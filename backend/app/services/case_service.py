"""Vụ án, người tham gia, đổi trạng thái / kháng cáo."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import AppealType, CaseRole, CaseStatus, UserRole
from app.db.models import CaseParticipant, CourtCase, User
from app.dependencies.case_member import roles_in_case
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError

# Vai trò tài khoản nào được giữ vai trò nào trong vụ
ALLOWED_CASE_ROLES = {
    UserRole.PARTY: {CaseRole.PLAINTIFF, CaseRole.DEFENDANT, CaseRole.LAWYER},
    UserRole.CLERK: {CaseRole.CLERK},
    UserRole.JUDGE: {CaseRole.JUDGE},
    UserRole.ADMIN: set(),
}
TRANSITIONS = {
    CaseStatus.OPEN: {CaseStatus.APPEAL, CaseStatus.CLOSED},
    CaseStatus.APPEAL: {CaseStatus.CLOSED},
    CaseStatus.CLOSED: set(),
}


def case_view(db: Session, case: CourtCase, user: User) -> dict:
    return {
        "id": str(case.id), "caseNumber": case.case_number, "title": case.title, "courtName": case.court_name,
        "status": case.status.value, "appealType": case.appeal_type.value if case.appeal_type else None,
        "myRoles": sorted(r.value for r in roles_in_case(db, case.id, user.id)),
    }


def create_case(db: Session, clerk: User, case_number: str, title: str, court_name: str | None) -> CourtCase:
    case_number = case_number.strip()
    if db.scalar(select(CourtCase.id).where(CourtCase.case_number == case_number)):
        raise AppError(409, ErrorCode.CASE_EXISTS, f"Đã có vụ án số {case_number}.")
    court = (court_name or clerk.court_name or "").strip()
    if not court:
        raise AppError(400, ErrorCode.VALIDATION_ERROR, "Cần courtName (tài khoản thư ký chưa có tòa).")
    case = CourtCase(case_number=case_number, title=title.strip(), court_name=court, created_by=clerk.id)
    db.add(case)
    db.flush()
    # Thư ký tạo vụ là thư ký của vụ, để thấy và thao tác được vụ đó
    db.add(CaseParticipant(case_id=case.id, user_id=clerk.id, role_in_case=CaseRole.CLERK))
    db.commit()
    return case


def list_cases(db: Session, user: User) -> list[CourtCase]:
    ids = select(CaseParticipant.case_id).where(CaseParticipant.user_id == user.id)
    return list(db.scalars(select(CourtCase).where(CourtCase.id.in_(ids)).order_by(CourtCase.case_number)))


def update_case(db: Session, case: CourtCase, status: CaseStatus | None, appeal_type: AppealType | None) -> CourtCase:
    new_status = status or case.status
    if new_status != case.status and new_status not in TRANSITIONS[case.status]:
        raise AppError(409, ErrorCode.INVALID_STATE,
                       f"Không chuyển được vụ từ {case.status.value} sang {new_status.value}.")
    if appeal_type and new_status != CaseStatus.APPEAL:
        raise AppError(409, ErrorCode.INVALID_STATE, "Chỉ ghi appealType khi vụ chuyển sang APPEAL.")
    if new_status == CaseStatus.APPEAL and not (appeal_type or case.appeal_type):
        raise AppError(409, ErrorCode.INVALID_STATE, "Chuyển sang APPEAL cần appealType (KHANG_CAO hoặc KHANG_NGHI).")
    case.status = new_status
    if appeal_type:
        case.appeal_type = appeal_type
    db.commit()
    return case


def lookup_user(db: Session, username: str | None, email: str | None) -> User:
    if username:
        user = db.scalar(select(User).where(User.username == username.strip().lower()))
    elif email:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
    else:
        raise AppError(400, ErrorCode.VALIDATION_ERROR, "Cần username hoặc email để tìm tài khoản.")
    if user is None:
        raise AppError(404, ErrorCode.USER_NOT_FOUND, "Không tìm thấy tài khoản.")
    return user


def add_participant(db: Session, case: CourtCase, user_id: uuid.UUID, role: CaseRole) -> CaseParticipant:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, ErrorCode.USER_NOT_FOUND, "Không tìm thấy tài khoản.")
    if role not in ALLOWED_CASE_ROLES[user.role]:
        raise AppError(400, ErrorCode.INVALID_PARTICIPANT_ROLE,
                       f"Tài khoản {user.role.value} không thể giữ vai trò {role.value} trong vụ.")
    if role in roles_in_case(db, case.id, user.id):
        raise AppError(409, ErrorCode.PARTICIPANT_EXISTS, "Người này đã có vai trò đó trong vụ.")
    participant = CaseParticipant(case_id=case.id, user_id=user.id, role_in_case=role)
    db.add(participant)
    db.commit()
    return participant


def list_participants(db: Session, case: CourtCase) -> list[tuple[CaseParticipant, User]]:
    return list(db.execute(select(CaseParticipant, User).join(User, CaseParticipant.user_id == User.id)
                           .where(CaseParticipant.case_id == case.id).order_by(CaseParticipant.role_in_case)).all())


def participant_view(participant: CaseParticipant, user: User) -> dict:
    return {"id": str(participant.id), "userId": str(user.id), "username": user.username, "fullName": user.full_name,
            "roleInCase": participant.role_in_case.value}


def remove_participant(db: Session, case: CourtCase, participant_id: uuid.UUID) -> None:
    participant = db.get(CaseParticipant, participant_id)
    if participant is None or participant.case_id != case.id:
        raise AppError(404, ErrorCode.PARTICIPANT_NOT_FOUND, "Không tìm thấy người tham gia trong vụ này.")
    db.delete(participant)
    db.commit()
