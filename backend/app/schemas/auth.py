from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.db.models import User

# Cắt khoảng trắng đầu/cuối trước khi kiểm (copy-paste hay dính dấu cách). Mật khẩu thì giữ nguyên.
Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50,
                                            pattern=r"^[A-Za-z0-9._-]+$")]
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class LoginRequest(BaseModel):
    username: Username
    password: str = Field(min_length=1, max_length=200)


def user_view(user: User) -> dict:
    return {"id": str(user.id), "username": user.username, "email": user.email, "fullName": user.full_name,
            "role": user.role.value, "courtName": user.court_name}
