"""/admin/users, /admin/access-logs (chỉ ADMIN)."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.enums import AccessResult, UserRole
from app.db.models import User
from app.db.session import get_db
from app.dependencies.roles import require_role
from app.schemas.admin import AdminUserCreate, AdminUserPatch
from app.schemas.auth import user_view
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_role(UserRole.ADMIN)


def admin_user_view(user: User) -> dict:
    return user_view(user) | {"status": user.status.value}


@router.post("/users", status_code=201)
def create_user(body: AdminUserCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    user, temporary = admin_service.create_user(db, body.username, body.email, body.full_name, body.role,
                                                body.court_name, body.password)
    view = admin_user_view(user)
    if temporary:
        view["temporaryPassword"] = temporary  # chỉ trả 1 lần, hãy gửi cho người dùng rồi đổi
    return view


@router.get("/users")
def list_users(q: str | None = None, role: UserRole | None = None, page: int = Query(1, ge=1),
               size: int = Query(20, ge=1, le=100), admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    rows, total = admin_service.list_users(db, q, role, page, size)
    return {"page": page, "size": size, "total": total, "items": [admin_user_view(u) for u in rows]}


@router.patch("/users/{user_id}")
def update_user(user_id: uuid.UUID, body: AdminUserPatch, admin: User = Depends(admin_only),
                db: Session = Depends(get_db)):
    user = admin_service.update_user(db, admin, user_id, body.full_name, body.role, body.status, body.court_name,
                                     body.password)
    return admin_user_view(user)


@router.get("/access-logs")
def list_access_logs(user_id: uuid.UUID | None = Query(None, alias="userId"),
                     case_id: uuid.UUID | None = Query(None, alias="caseId"),
                     result: AccessResult | None = None, start: datetime | None = Query(None, alias="from"),
                     end: datetime | None = Query(None, alias="to"), page: int = Query(1, ge=1),
                     size: int = Query(50, ge=1, le=200), admin: User = Depends(admin_only),
                     db: Session = Depends(get_db)):
    """Ai làm gì, vào vụ nào, lúc nào — có cả thao tác bị từ chối (DENY)."""
    rows, total = admin_service.list_access_logs(db, user_id, case_id, result, start, end, page, size)
    return {"page": page, "size": size, "total": total,
            "items": [admin_service.access_log_view(log, user) for log, user in rows]}
