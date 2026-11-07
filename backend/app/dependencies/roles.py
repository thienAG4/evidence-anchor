"""require_role(...)."""
from fastapi import Depends

from app.db.enums import UserRole
from app.db.models import User
from app.dependencies.auth import get_current_user
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError


def require_role(*roles: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            allowed = ", ".join(r.value for r in roles)
            raise AppError(403, ErrorCode.FORBIDDEN, f"Chức năng này chỉ dành cho: {allowed}.")
        return user
    return dependency
