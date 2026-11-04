import uuid

from pydantic import Field

from app.db.enums import AppealType, CaseRole, CaseStatus
from app.schemas.common import CamelModel


class CaseCreate(CamelModel):
    case_number: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=300)
    court_name: str | None = Field(None, max_length=200)  # trống: lấy tòa của thư ký


class CasePatch(CamelModel):
    status: CaseStatus | None = None
    appeal_type: AppealType | None = None


class ParticipantCreate(CamelModel):
    user_id: uuid.UUID
    role_in_case: CaseRole
