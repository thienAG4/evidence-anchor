"""Đọc token, lấy user hiện tại."""
import uuid

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.enums import UserStatus
from app.db.models import User
from app.db.session import get_db
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError

bearer = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise AppError(401, ErrorCode.UNAUTHENTICATED, "Cần đăng nhập (header Authorization: Bearer <token>).")
    try:
        user_id = uuid.UUID(decode_access_token(credentials.credentials)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AppError(401, ErrorCode.UNAUTHENTICATED, "Token không hợp lệ hoặc đã hết hạn.") from None
    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AppError(401, ErrorCode.UNAUTHENTICATED, "Tài khoản không tồn tại hoặc đã bị khóa.")
    return user
