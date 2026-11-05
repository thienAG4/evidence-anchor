"""GET /anchor/schedule (công khai), POST /anchor/now (nút "Neo ngay", người đã đăng nhập)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.services import anchor_service

router = APIRouter(prefix="/anchor", tags=["anchor"])


@router.get("/schedule")
def get_schedule(db: Session = Depends(get_db)):
    """Chế độ neo, mốc khóa kế tiếp của bản ghi đang chờ, số bản ghi đang chờ, job neo có đang dừng không."""
    return anchor_service.schedule(db)


@router.post("/now", status_code=202)
def anchor_now(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ghi yêu cầu Neo ngay. Worker chốt các bản ghi đang chờ ở vòng kế (ANCHOR_INTERVAL_SECONDS).

    Bấm nhiều lần chỉ giữ một yêu cầu; không có bản ghi chờ thì worker không gửi giao dịch nào."""
    anchor_service.request_anchor_now(db)
    return anchor_service.schedule(db)
