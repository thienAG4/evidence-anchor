"""Nộp lô tại Tòa (F2, F3, F7): băm file, so với bản lưu chứng, hash tổng lô, đánh số lô; tính lại hash tổng.

Mọi bản ghi chỉ ghi thêm: kết quả tính lại nằm ở IntegrityCheck, không sửa Submission / FileHash.
"""
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.hashing import (LOT_SCHEME, compute_lot_bundle, create_lot_bundle, hash_concat, hash_evidence,
                              hash_stream, now_vn)
from app.core.log_record import EVENT_E
from app.core.receipt import build_receipt, sign
from app.db.enums import CaseStatus, CheckTarget, FileResult, MatchResult, SubmissionType
from app.db.models import CourtCase, FileHash, IntegrityCheck, Submission, User
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError
from app.labels import DISCLAIMER, file_result, recorded_result
from app.services.anchor_service import anchor_state
from app.services.log_service import append_record, result_code, unix_seconds
from app.services.submission_service import next_receipt_code


def find_baseline(db: Session, file_code: str) -> tuple[FileHash, Submission, User]:
    """Bản lưu chứng (A) theo mã file đương sự ghi trong danh mục (F7). Chỉ tìm trong lưu chứng SELF."""
    row = db.execute(
        select(FileHash, Submission, User).join(Submission, FileHash.submission_id == Submission.id)
        .join(User, Submission.owner_id == User.id)
        .where(FileHash.file_code == file_code.strip().upper(), Submission.type == SubmissionType.SELF)
    ).first()
    if row is None:
        raise AppError(404, ErrorCode.FILE_CODE_NOT_FOUND, f"Mã '{file_code}' không có bản lưu chứng nào.")
    return row[0], row[1], row[2]


def parse_meta(meta: str | None, file_count: int) -> list[str | None]:
    """meta = JSON [{"fileCode": "TX-0001-1"}, {"fileCode": ""}, ...] cùng thứ tự files[]; trống = không có mã."""
    if not meta:
        return [None] * file_count
    try:
        items = json.loads(meta)
        codes = [(item.get("fileCode") or "").strip() or None for item in items]
    except (json.JSONDecodeError, AttributeError, TypeError):
        raise AppError(400, ErrorCode.META_MISMATCH,
                       'meta phải là JSON dạng [{"fileCode": "TX-0001-1"}, {"fileCode": ""}]') from None
    if len(codes) != file_count:
        raise AppError(400, ErrorCode.META_MISMATCH,
                       f"meta có {len(codes)} dòng nhưng gửi {file_count} file; phải cùng số lượng và thứ tự.")
    return codes


def create_lot(db: Session, case: CourtCase, clerk: User, place: str | None, file_codes: list[str | None],
               items: list[tuple[str, BinaryIO]]) -> Submission:
    if case.status == CaseStatus.CLOSED:
        raise AppError(409, ErrorCode.CASE_CLOSED, "Vụ án đã đóng, không nhận lô mới.")
    place = (place or clerk.court_name or case.court_name).strip()
    # Mã sai thì báo lỗi, không lưu, không so (F7-AC2) -> kiểm tra trước khi băm
    baselines = [find_baseline(db, code)[0] if code else None for code in file_codes]

    submitted_at = now_vn()
    entries = hash_evidence(items)  # giờ do server cấp (F2-AC2)
    bundle = create_lot_bundle(entries, place)  # hash tổng: giờ, nơi nộp, số lượng, hash từng file (F3-AC4)
    checked_at = datetime.now(timezone.utc)

    db.execute(select(CourtCase.id).where(CourtCase.id == case.id).with_for_update())  # 2 lô cùng lúc không trùng số
    lot_no = (db.scalar(select(func.max(Submission.lot_no)).where(Submission.case_id == case.id)) or 0) + 1
    code = next_receipt_code(db)
    files = []
    for i, (entry, baseline) in enumerate(zip(entries, baselines), 1):
        if baseline is None:
            result = FileResult.NO_BASELINE  # hash lúc nhận làm mốc (F3-AC3)
        elif baseline.file_hash == entry["fileHash"]:
            result = FileResult.UNCHANGED
        else:
            result = FileResult.CHANGED  # không kết luận có người sửa (F3-AC2)
        files.append({**entry, "position": i, "fileCode": f"{code}-{i}", "baseline": baseline, "result": result})

    receipt = build_receipt(
        receipt_code=code, submission_type=SubmissionType.COURT_LOT.value,
        owner={"id": str(clerk.id), "fullName": clerk.full_name}, submitted_at=submitted_at,
        scheme=LOT_SCHEME, files=files, bundle=bundle,
        extra={"caseNumber": case.case_number, "lotNo": lot_no, "place": place, "fileCount": len(files)},
    )
    lot = Submission(
        receipt_code=code, type=SubmissionType.COURT_LOT, owner_id=clerk.id, case_id=case.id, lot_no=lot_no,
        place=place, file_count=len(files), submitted_at=datetime.fromisoformat(submitted_at),
        bundle_scheme=LOT_SCHEME, habc=bundle["habc"], bundled_at=bundle["bundledAt"],
        bundle_time_hash=bundle["bundleTimeHash"], lot_meta_hash=bundle["lotMetaHash"],
        bundle_hash=bundle["bundleHash"], signature=sign(receipt), receipt_json=receipt,
    )
    db.add(lot)
    db.flush()
    for f in files:
        sleep = f.get("sleepAfterSeconds")
        record = append_record(db, event_type=EVENT_E, file_hash=f["fileHash"], actor_id=clerk.id,
                               ts=unix_seconds(f["hashedAt"]), result=result_code(f["result"]), case_id=case.id,
                               ref_seq=f["baseline"].record_seq if f["baseline"] else None)  # E trỏ A
        db.add(FileHash(
            submission_id=lot.id, position=f["position"], file_name=f["fileName"][:255], file_code=f["fileCode"],
            file_hash=f["fileHash"], hashed_at=f["hashedAt"], time_hash=f["timeHash"], leaf_hash=f["leafHash"],
            sleep_after_seconds=Decimal(str(sleep)) if sleep is not None else None,
            baseline_file_id=f["baseline"].id if f["baseline"] else None, result=f["result"], checked_at=checked_at,
            record_seq=record.seq,
        ))
    db.commit()
    return lot


def get_lot(db: Session, case: CourtCase, lot_id: uuid.UUID) -> Submission:
    lot = db.get(Submission, lot_id)
    if lot is None or lot.case_id != case.id or lot.type != SubmissionType.COURT_LOT:
        raise AppError(404, ErrorCode.LOT_NOT_FOUND, "Không tìm thấy lô trong vụ này.")
    return lot


def get_evidence(db: Session, case: CourtCase, evidence_id: uuid.UUID) -> FileHash:
    """Chứng cứ = 1 file trong 1 lô của vụ này."""
    row = db.execute(select(FileHash, Submission).join(Submission, FileHash.submission_id == Submission.id)
                     .where(FileHash.id == evidence_id)).first()
    if row is None or row[1].case_id != case.id or row[1].type != SubmissionType.COURT_LOT:
        raise AppError(404, ErrorCode.EVIDENCE_NOT_FOUND, "Không tìm thấy chứng cứ trong vụ này.")
    return row[0]


def latest_check(db: Session, **target) -> IntegrityCheck | None:
    column, value = next(iter(target.items()))
    return db.scalar(select(IntegrityCheck).where(getattr(IntegrityCheck, column) == value)
                     .order_by(IntegrityCheck.checked_at.desc()).limit(1))


def lot_view(db: Session, lot: Submission, show_baseline: bool) -> dict:
    """Kết quả để công bố (F5): không có mã hash; mỗi kết quả kèm 'Kiểm tra lúc'."""
    check = latest_check(db, submission_id=lot.id)
    # Chưa tính lại lần nào: lô khớp chính nó tại lúc nhận
    lot_result = recorded_result(check.result, check.checked_at) if check else recorded_result(
        MatchResult.UNCHANGED, lot.submitted_at)
    status, _ = anchor_state(db, lot.id)
    files = []
    for f in db.scalars(select(FileHash).where(FileHash.submission_id == lot.id).order_by(FileHash.position)):
        item = {"evidenceId": str(f.id), "position": f.position, "fileName": f.file_name, "fileCode": f.file_code,
                "result": file_result(f.result, f.checked_at)}
        recheck = latest_check(db, file_id=f.id)
        item["recordedCheck"] = recorded_result(recheck.result, recheck.checked_at) if recheck else None
        if show_baseline and f.baseline_file_id:  # thư ký thấy giờ lưu chứng và người lưu, không thấy file (F7)
            baseline, sub, owner = find_baseline(db, db.get(FileHash, f.baseline_file_id).file_code)
            item["baseline"] = {"fileCode": baseline.file_code, "hashedAt": baseline.hashed_at,
                                "ownerName": owner.full_name}
        files.append(item)
    return {
        "lotId": str(lot.id), "lotNo": lot.lot_no, "receiptCode": lot.receipt_code,
        "receivedAt": lot.receipt_json["submittedAt"], "place": lot.place, "fileCount": lot.file_count,
        "anchorStatus": status.value, "result": lot_result, "files": files, "disclaimer": DISCLAIMER,
    }


def list_lots(db: Session, case: CourtCase) -> list[Submission]:
    return list(db.scalars(select(Submission).where(Submission.case_id == case.id,
                                                    Submission.type == SubmissionType.COURT_LOT)
                           .order_by(Submission.lot_no)))


def recheck_lot(db: Session, lot: Submission, clerk: User, streams: list[BinaryIO]) -> IntegrityCheck:
    """F3-AC5: tính lại hash tổng từ file chọn lại + giờ, nơi, số lượng đọc từ bản ghi lô.

    Mỗi file chọn lại phải trùng hash một file của lô (lấy giờ băm đã lưu của file đó); thêm, bớt, đổi file
    hay bản ghi lô bị sửa đều làm hash tổng khác.
    """
    times_by_hash = defaultdict(list)
    for f in db.scalars(select(FileHash).where(FileHash.submission_id == lot.id).order_by(FileHash.position)):
        times_by_hash[f.file_hash].append(f.hashed_at)
    entries, hashes, unknown = [], [], False
    for stream in streams:
        file_hash = hash_stream(stream)
        hashes.append(file_hash)
        if times_by_hash[file_hash]:
            entries.append({"fileHash": file_hash, "hashedAt": times_by_hash[file_hash].pop(0)})
        else:
            unknown = True  # file không thuộc lô (hoặc đã bị sửa)
    if unknown or not entries:
        result = MatchResult.CHANGED
        # Không tính được hash tổng: bản ghi E giữ dấu vân tay của bộ file đã chọn
        observed = hash_concat(*sorted(hashes)) if hashes else lot.bundle_hash
    else:
        observed = compute_lot_bundle(entries, lot.bundled_at, lot.place, lot.file_count)["bundleHash"]
        result = MatchResult.UNCHANGED if observed == lot.bundle_hash else MatchResult.CHANGED
    return _record_check(db, clerk, result, observed, lot.case_id, None, target=CheckTarget.LOT, submission_id=lot.id)


def recheck_evidence(db: Session, evidence: FileHash, clerk: User, stream: BinaryIO) -> IntegrityCheck:
    """So file chọn lại với hash đã ghi lúc nhận (E)."""
    file_hash = hash_stream(stream)
    result = MatchResult.UNCHANGED if file_hash == evidence.file_hash else MatchResult.CHANGED
    case_id = db.get(Submission, evidence.submission_id).case_id
    return _record_check(db, clerk, result, file_hash, case_id, evidence.record_seq,
                         target=CheckTarget.FILE, file_id=evidence.id)


def _record_check(db: Session, user: User, result: MatchResult, observed_hash: str, case_id, ref_seq,
                  **fields) -> IntegrityCheck:
    checked_at = datetime.now(timezone.utc)
    record = append_record(db, event_type=EVENT_E, file_hash=observed_hash, actor_id=user.id,
                           ts=unix_seconds(checked_at), result=result_code(result), case_id=case_id, ref_seq=ref_seq)
    check = IntegrityCheck(result=result, checked_by=user.id, checked_at=checked_at, record_seq=record.seq, **fields)
    db.add(check)
    db.commit()
    return check


def check_view(check: IntegrityCheck) -> dict:
    return {**recorded_result(check.result, check.checked_at), "disclaimer": DISCLAIMER}


def baseline_view(db: Session, file_code: str) -> dict:
    baseline, _, owner = find_baseline(db, file_code)
    return {"fileCode": baseline.file_code, "hashedAt": baseline.hashed_at, "ownerName": owner.full_name}
