"""/cases, /cases/{id}/participants, /users/lookup."""
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.enums import CaseRole, UserRole
from app.db.models import CourtCase, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.case_member import case_clerk, case_member
from app.dependencies.roles import require_role
from app.schemas.auth import user_view
from app.schemas.case import CaseCreate, CasePatch, ParticipantCreate
from app.services import case_service

router = APIRouter(tags=["cases"])
clerk_only = require_role(UserRole.CLERK)


@router.post("/cases", status_code=201)
def create_case(body: CaseCreate, user: User = Depends(clerk_only), db: Session = Depends(get_db)):
    case = case_service.create_case(db, user, body.case_number, body.title, body.court_name)
    return case_service.case_view(db, case, user)


@router.get("/cases")
def list_cases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Chỉ vụ mình tham gia."""
    return {"items": [case_service.case_view(db, c, user) for c in case_service.list_cases(db, user)]}


@router.get("/cases/{case_id}")
def get_case(case: CourtCase = Depends(case_member()), user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    return case_service.case_view(db, case, user)


@router.patch("/cases/{case_id}")
def update_case(body: CasePatch, case: CourtCase = Depends(case_clerk), user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    case = case_service.update_case(db, case, body.status, body.appeal_type)
    return case_service.case_view(db, case, user)


@router.get("/users/lookup")
def lookup_user(username: str | None = Query(None), email: str | None = Query(None),
                user: User = Depends(clerk_only), db: Session = Depends(get_db)):
    """Thư ký tìm tài khoản theo tên đăng nhập (hoặc email) để thêm vào vụ."""
    found = user_view(case_service.lookup_user(db, username, email))
    return {k: found[k] for k in ("id", "username", "fullName", "role")}


@router.post("/cases/{case_id}/participants", status_code=201)
def add_participant(body: ParticipantCreate, case: CourtCase = Depends(case_clerk), db: Session = Depends(get_db)):
    participant = case_service.add_participant(db, case, body.user_id, body.role_in_case)
    return case_service.participant_view(participant, db.get(User, participant.user_id))


@router.get("/cases/{case_id}/participants")
def list_participants(case: CourtCase = Depends(case_member(CaseRole.CLERK, CaseRole.JUDGE)),
                      db: Session = Depends(get_db)):
    return {"items": [case_service.participant_view(p, u) for p, u in case_service.list_participants(db, case)]}


@router.delete("/cases/{case_id}/participants/{participant_id}", status_code=204)
def remove_participant(participant_id: uuid.UUID, case: CourtCase = Depends(case_clerk),
                       db: Session = Depends(get_db)):
    case_service.remove_participant(db, case, participant_id)
    return Response(status_code=204)
