"""Biên nhận lưu chứng (SELF) cho giao diện: đương sự xem của mình, thư ký xem và đối chiếu.

Thư ký chỉ thấy biên nhận của đương sự thuộc các vụ mình là thư ký (F8-AC3). Kết quả đối chiếu ghi thêm vào
IntegrityCheck (target FILE, file_id = file trong biên nhận), không sửa biên nhận.
"""
from datetime import datetime, timezone
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.hashing import hash_stream
from app.db.enums import AnchorStatus, CaseRole, CheckTarget, MatchResult, SubmissionType, UserRole
from app.db.models import CaseParticipant, FileHash, IntegrityCheck, Submission, User
from app.dependencies.case_member import PARTY_CASE_ROLES
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError
from app.labels import ANCHOR_STATUS_LABELS, DISCLAIMER, file_result, vn_time
from app.services.anchor_service import anchor_state


def _latest_checks(db: Session, file_ids: list) -> dict:
    """file_id -> IntegrityCheck mới nhất."""
    latest = {}
    for check in db.scalars(select(IntegrityCheck).where(IntegrityCheck.file_id.in_(file_ids))
                            .order_by(IntegrityCheck.checked_at)):
        latest[check.file_id] = check
    return latest


def receipt_view(db: Session, submission: Submission, include_hashes: bool = False) -> dict:
    """Biên nhận + kết quả Tòa đối chiếu từng file. include_hashes chỉ cho chủ biên nhận (tự kiểm tra)."""
    owner = db.get(User, submission.owner_id)
    status, anchor, _ = anchor_state(db, submission.id)
    files = list(db.scalars(select(FileHash).where(FileHash.submission_id == submission.id)
                            .order_by(FileHash.position)))
    checks = _latest_checks(db, [f.id for f in files])
    items = []
    for f in files:
        check = checks.get(f.id)
        item = {"fileCode": f.file_code, "fileName": f.file_name, "hashedAt": f.hashed_at,
                "result": file_result(check.result, check.checked_at) if check else None,
                "phase": check.phase if check else None}
        if include_hashes:
            item["fileHash"] = f.file_hash
        items.append(item)
    return {
        "receiptCode": submission.receipt_code,
        "owner": {"id": str(owner.id), "fullName": owner.full_name},
        "submittedAt": submission.receipt_json["submittedAt"],
        "fileCount": submission.file_count,
        "status": status.value, "statusLabel": ANCHOR_STATUS_LABELS[status.value],
        "anchoredAt": vn_time(anchor.block_time) if status == AnchorStatus.ANCHORED and anchor else None,
        "checked": any(checks.values()),
        "files": items,
        "disclaimer": DISCLAIMER,
    }


def parties_of_clerk(db: Session, clerk: User) -> list[User]:
    """Đương sự (nguyên đơn, bị đơn, luật sư) trong các vụ mà user này là thư ký."""
    case_ids = select(CaseParticipant.case_id).where(CaseParticipant.user_id == clerk.id,
                                                     CaseParticipant.role_in_case == CaseRole.CLERK)
    user_ids = select(CaseParticipant.user_id).where(CaseParticipant.case_id.in_(case_ids),
                                                     CaseParticipant.role_in_case.in_(PARTY_CASE_ROLES))
    return list(db.scalars(select(User).where(User.id.in_(user_ids), User.role == UserRole.PARTY)
                           .order_by(User.full_name)))


def receipts_for_clerk(db: Session, clerk: User) -> list[Submission]:
    owner_ids = [u.id for u in parties_of_clerk(db, clerk)]
    if not owner_ids:
        return []
    return list(db.scalars(select(Submission).where(Submission.type == SubmissionType.SELF,
                                                    Submission.owner_id.in_(owner_ids))
                           .order_by(Submission.submitted_at.desc())))


def receipt_for_clerk(db: Session, clerk: User, code: str) -> Submission:
    submission = db.scalar(select(Submission).where(Submission.receipt_code == code.strip().upper(),
                                                    Submission.type == SubmissionType.SELF))
    if submission is None or submission.owner_id not in {u.id for u in parties_of_clerk(db, clerk)}:
        raise AppError(404, ErrorCode.RECEIPT_NOT_FOUND,
                       "Không có lần lưu chứng cứ này, hoặc đương sự không thuộc vụ án bạn phụ trách.")
    return submission


def _file_in_receipt(db: Session, submission: Submission, file_code: str) -> FileHash:
    f = db.scalar(select(FileHash).where(FileHash.submission_id == submission.id,
                                         FileHash.file_code == file_code.strip().upper()))
    if f is None:
        raise AppError(404, ErrorCode.FILE_CODE_NOT_FOUND, f"Biên nhận {submission.receipt_code} không có mã {file_code}.")
    return f


def _require_anchored(db: Session, submission: Submission) -> None:
    if not settings.require_anchor_before_verify:
        return
    status, _, _ = anchor_state(db, submission.id)
    if status != AnchorStatus.ANCHORED:
        raise AppError(409, ErrorCode.INVALID_STATE,
                       f"Lần lưu chứng cứ {submission.receipt_code} chưa khóa (chưa neo lên chuỗi), chưa đối chiếu được.")


def compare(db: Session, submission: Submission, file_code: str, stream: BinaryIO) -> MatchResult:
    """So file Tòa chọn với file cùng mã trong biên nhận. Chỉ trả kết quả, KHÔNG ghi."""
    _require_anchored(db, submission)
    target = _file_in_receipt(db, submission, file_code)
    return MatchResult.UNCHANGED if hash_stream(stream) == target.file_hash else MatchResult.CHANGED


def save_verification(db: Session, clerk: User, submission: Submission, phase: str,
                      items: list[tuple[str, BinaryIO]]) -> list[tuple[FileHash, IntegrityCheck]]:
    """Băm lại từng file trên server (không tin kết quả từ trình duyệt) rồi ghi thêm kết quả, kèm giai đoạn."""
    _require_anchored(db, submission)
    targets = [_file_in_receipt(db, submission, code) for code, _ in items]
    if len({t.id for t in targets}) != len(targets):
        raise AppError(400, ErrorCode.META_MISMATCH, "Mỗi mã file chỉ đối chiếu 1 lần trong 1 lần lưu kết quả.")
    now = datetime.now(timezone.utc)
    saved = []
    for target, (_, stream) in zip(targets, items):
        result = MatchResult.UNCHANGED if hash_stream(stream) == target.file_hash else MatchResult.CHANGED
        check = IntegrityCheck(target=CheckTarget.FILE, file_id=target.id, result=result, phase=phase.strip()[:100],
                               checked_by=clerk.id, checked_at=now)
        db.add(check)
        saved.append((target, check))
    db.commit()
    return saved


def litigants_for_clerk(db: Session, clerk: User) -> list[dict]:
    rows = []
    receipts = receipts_for_clerk(db, clerk)
    for party in parties_of_clerk(db, clerk):
        own = [s for s in receipts if s.owner_id == party.id]
        rows.append({"id": str(party.id), "username": party.username, "fullName": party.full_name,
                     "email": party.email, "receiptCount": len(own), "fileCount": sum(s.file_count for s in own),
                     "lastSubmittedAt": own[0].receipt_json["submittedAt"] if own else None})
    return rows
