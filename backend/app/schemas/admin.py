from pydantic import Field

from app.db.enums import UserRole, UserStatus
from app.schemas.auth import Email, Username
from app.schemas.common import CamelModel


class AdminUserCreate(CamelModel):
    username: Username
    email: Email
    full_name: str = Field(min_length=1, max_length=150)
    role: UserRole
    court_name: str | None = Field(None, max_length=200)
    password: str | None = Field(None, min_length=4, max_length=200)  # trống: hệ thống sinh mật khẩu tạm


class AdminUserPatch(CamelModel):
    full_name: str | None = Field(None, min_length=1, max_length=150)
    role: UserRole | None = None
    status: UserStatus | None = None
    court_name: str | None = Field(None, max_length=200)
    password: str | None = Field(None, min_length=4, max_length=200)  # đặt lại mật khẩu
