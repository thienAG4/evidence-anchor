"""Kiểm tra user có tham gia vụ không (F8-AC3: người ngoài vụ không thấy gì)."""
import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import CaseRole, UserRole
from app.db.models import CaseParticipant, CourtCase, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError

PARTY_CASE_ROLES = {CaseRole.PLAINTIFF, CaseRole.DEFENDANT, CaseRole.LAWYER}


def get_case(db: Session, case_id: uuid.UUID) -> CourtCase:
    case = db.get(CourtCase, case_id)
    if case is None:
        raise AppError(404, ErrorCode.CASE_NOT_FOUND, "Không tìm thấy vụ án.")
    return case


def roles_in_case(db: Session, case_id: uuid.UUID, user_id: uuid.UUID) -> set[CaseRole]:
    return set(db.scalars(select(CaseParticipant.role_in_case).where(
        CaseParticipant.case_id == case_id, CaseParticipant.user_id == user_id)))


def require_case_access(db: Session, case_id: uuid.UUID, user: User,
                        allowed: set[CaseRole] | None = None) -> CourtCase:
    """Vụ phải tồn tại, user phải tham gia vụ (và đúng vai trò trong vụ nếu có `allowed`)."""
    case = get_case(db, case_id)
    roles = roles_in_case(db, case.id, user.id)
    if not roles or (allowed and not roles & allowed):
        raise AppError(403, ErrorCode.NOT_CASE_PARTICIPANT, "Bạn không tham gia vụ án này hoặc không có quyền thao tác.")
    return case


def case_member(*allowed: CaseRole):
    """Dependency cho route có {case_id}: trả về vụ án nếu user được phép."""
    def dependency(case_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return require_case_access(db, case_id, user, set(allowed) or None)
    return dependency


def case_clerk(case_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CourtCase:
    """Thư ký (vai trò tài khoản CLERK) đang là thư ký của vụ này."""
    if user.role != UserRole.CLERK:
        raise AppError(403, ErrorCode.FORBIDDEN, "Chức năng này chỉ dành cho: CLERK.")
    return require_case_access(db, case_id, user, {CaseRole.CLERK})
