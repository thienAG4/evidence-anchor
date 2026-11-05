"""Lưu chứng của đương sự (F1): băm file, tạo biên nhận, ghi Submission + FileHash + bản ghi A (chỉ ghi thêm)."""
from datetime import datetime
from decimal import Decimal
from typing import BinaryIO

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.hashing import BUNDLE_SCHEME, create_bundle, hash_evidence, hash_stream, now_vn
from app.core.log_record import EVENT_A
from app.core.receipt import build_receipt, record_signature, sign
from app.db.enums import SubmissionType
from app.db.models import FileHash, Submission, User
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError
from app.services.log_service import append_record, unix_seconds


def next_receipt_code(db: Session) -> str:
    """TX-0001, TX-0002... lấy từ sequence nên 2 request cùng lúc không trùng mã."""
    n = db.execute(text("SELECT nextval('receipt_code_seq')")).scalar_one()
    return f"TX-{n:04d}"


def create_self_submission(db: Session, owner: User, items: list[tuple[str, BinaryIO]]) -> Submission:
    submitted_at = now_vn()
    entries = hash_evidence(items)  # giờ do server cấp, nghỉ 1–3 giây giữa các file
    bundle = create_bundle(entries)
    code = next_receipt_code(db)
    files = [{**e, "position": i, "fileCode": f"{code}-{i}"} for i, e in enumerate(entries, 1)]
    # Bản ghi A trước: biên nhận chứa seq, recordHash và chữ ký trên từng bản ghi (58 byte)
    for f in files:
        record = append_record(db, event_type=EVENT_A, file_hash=f["fileHash"], actor_id=owner.id,
                               ts=unix_seconds(f["hashedAt"]))
        f.update(seq=record.seq, recordHash=record.record_hash,
                 recordSignature=record_signature(record.seq, record.record_hash))

    receipt = build_receipt(
        receipt_code=code, submission_type=SubmissionType.SELF.value,
        owner={"id": str(owner.id), "fullName": owner.full_name},
        submitted_at=submitted_at, scheme=BUNDLE_SCHEME, files=files, bundle=bundle,
    )
    submission = Submission(
        receipt_code=code, type=SubmissionType.SELF, owner_id=owner.id, file_count=len(files),
        submitted_at=datetime.fromisoformat(submitted_at), bundle_scheme=BUNDLE_SCHEME,
        habc=bundle["habc"], bundled_at=bundle["bundledAt"], bundle_time_hash=bundle["bundleTimeHash"],
        bundle_hash=bundle["bundleHash"], signature=sign(receipt), receipt_json=receipt,
    )
    db.add(submission)
    db.flush()
    for f in files:
        sleep = f.get("sleepAfterSeconds")
        db.add(FileHash(
            submission_id=submission.id, position=f["position"], file_name=f["fileName"][:255],
            file_code=f["fileCode"], file_hash=f["fileHash"], hashed_at=f["hashedAt"],
            time_hash=f["timeHash"], leaf_hash=f["leafHash"],
            sleep_after_seconds=Decimal(str(sleep)) if sleep is not None else None, record_seq=f["seq"],
        ))
    db.commit()
    return submission


def list_own(db: Session, owner: User, page: int, size: int) -> tuple[list[Submission], int]:
    where = (Submission.owner_id == owner.id, Submission.type == SubmissionType.SELF)
    total = db.scalar(select(func.count()).select_from(Submission).where(*where))
    rows = db.scalars(select(Submission).where(*where).order_by(Submission.submitted_at.desc())
                      .offset((page - 1) * size).limit(size)).all()
    return list(rows), total


def get_own_by_code(db: Session, owner: User, code: str) -> Submission:
    """Không phải của mình cũng báo 'không tìm thấy', không để lộ mã nào tồn tại."""
    submission = db.scalar(select(Submission).where(Submission.receipt_code == code.strip().upper()))
    if submission is None or submission.owner_id != owner.id or submission.type != SubmissionType.SELF:
        raise AppError(404, ErrorCode.RECEIPT_NOT_FOUND, "Không tìm thấy biên nhận.")
    return submission


def lookup_by_file(db: Session, owner: User, stream: BinaryIO) -> tuple[FileHash, Submission]:
    """F1-AC4: chủ tài khoản đưa lại file -> tìm bản lưu chứng sớm nhất của chính họ."""
    file_hash = hash_stream(stream)
    row = db.execute(
        select(FileHash, Submission).join(Submission, FileHash.submission_id == Submission.id)
        .where(FileHash.file_hash == file_hash, Submission.owner_id == owner.id,
               Submission.type == SubmissionType.SELF)
        .order_by(Submission.submitted_at, FileHash.position).limit(1)
    ).first()
    if row is None:
        raise AppError(404, ErrorCode.RECORD_NOT_FOUND, "Không tìm thấy bản lưu chứng nào của bạn khớp với tệp này.")
    return row[0], row[1]
