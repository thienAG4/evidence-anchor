"""/auth/login, /auth/logout, /me."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.auth import LoginRequest, user_view
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Đăng nhập bằng tài khoản có sẵn, ví dụ duongsu / 1234, thuky / 5678."""
    user = auth_service.login(db, body.username, body.password)
    return {"token": create_access_token(user.id, user.role.value), "user": user_view(user)}


@router.post("/auth/logout", status_code=204)
def logout(user: User = Depends(get_current_user)):
    """JWT không lưu phía server: client tự xóa token. Token cũ vẫn dùng được tới khi hết hạn."""
    return Response(status_code=204)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_view(user)
