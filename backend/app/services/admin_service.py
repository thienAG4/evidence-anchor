"""Quản lý tài khoản (mọi vai trò, không có tự đăng ký), đọc nhật ký truy cập."""
import secrets
import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.enums import AccessResult, UserRole, UserStatus
from app.db.models import AccessLog, User
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError
from app.labels import vn_time


def create_user(db: Session, username: str, email: str, full_name: str, role: UserRole, court_name: str | None,
                password: str | None) -> tuple[User, str | None]:
    """Tạo tài khoản. Không nhập mật khẩu thì sinh mật khẩu tạm (trả về 1 lần)."""
    username, email = username.strip().lower(), email.strip().lower()
    if db.scalar(select(User.id).where(User.username == username)):
        raise AppError(409, ErrorCode.USERNAME_EXISTS, "Tên đăng nhập đã có người dùng.")
    if db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, ErrorCode.EMAIL_EXISTS, "Email đã có tài khoản.")
    temporary = None if password else secrets.token_urlsafe(9)
    user = User(username=username, email=email, full_name=full_name.strip(), role=role, court_name=court_name,
                password_hash=hash_password(password or temporary))
    db.add(user)
    db.commit()
    return user, temporary


def list_users(db: Session, q: str | None, role: UserRole | None, page: int, size: int) -> tuple[list[User], int]:
    where = []
    if q:
        pattern = f"%{q.strip().lower()}%"
        where.append(or_(User.username.like(pattern), func.lower(User.email).like(pattern),
                         func.lower(User.full_name).like(pattern)))
    if role:
        where.append(User.role == role)
    total = db.scalar(select(func.count()).select_from(User).where(*where))
    rows = db.scalars(select(User).where(*where).order_by(User.username).offset((page - 1) * size).limit(size))
    return list(rows), total


def update_user(db: Session, admin: User, user_id: uuid.UUID, full_name: str | None, role: UserRole | None,
                status: UserStatus | None, court_name: str | None, password: str | None = None) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, ErrorCode.USER_NOT_FOUND, "Không tìm thấy tài khoản.")
    if user.id == admin.id and (status == UserStatus.DISABLED or (role and role != UserRole.ADMIN)):
        raise AppError(409, ErrorCode.INVALID_STATE, "Không tự khóa hay tự bỏ quyền quản trị của chính mình.")
    if password:
        user.password_hash = hash_password(password)
    if full_name:
        user.full_name = full_name.strip()
    if role:
        user.role = role
    if status:
        user.status = status
    if court_name is not None:
        user.court_name = court_name or None
    db.commit()
    return user


def list_access_logs(db: Session, user_id: uuid.UUID | None, case_id: uuid.UUID | None,
                     result: AccessResult | None, start: datetime | None, end: datetime | None,
                     page: int, size: int) -> tuple[list[tuple[AccessLog, User | None]], int]:
    where = []
    if user_id:
        where.append(AccessLog.user_id == user_id)
    if case_id:
        where.append(AccessLog.case_id == case_id)
    if result:
        where.append(AccessLog.result == result)
    if start:
        where.append(AccessLog.created_at >= start)
    if end:
        where.append(AccessLog.created_at <= end)
    total = db.scalar(select(func.count()).select_from(AccessLog).where(*where))
    rows = db.execute(select(AccessLog, User).outerjoin(User, AccessLog.user_id == User.id).where(*where)
                      .order_by(AccessLog.id.desc()).offset((page - 1) * size).limit(size)).all()
    return [(log, user) for log, user in rows], total


def access_log_view(log: AccessLog, user: User | None) -> dict:
    return {"id": log.id, "at": vn_time(log.created_at), "userId": str(log.user_id) if log.user_id else None,
            "username": user.username if user else None, "role": log.role, "action": log.action,
            "resource": log.resource, "caseId": str(log.case_id) if log.case_id else None,
            "result": log.result.value, "ip": str(log.ip) if log.ip else None}
