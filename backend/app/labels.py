"""Ánh xạ giá trị DB sang nhãn hiển thị (API và giao diện không bao giờ trả giá trị thô hay mã hash)."""
from datetime import datetime

from app.core.hashing import vietnam_tz

DISCLAIMER = "Chỉ so với bản đã lưu, không xác định thật giả."

# So 1 file với bản lưu chứng (A)
FILE_LABELS = {
    "UNCHANGED": "KHỚP BẢN LƯU CHỨNG",
    "CHANGED": "KHÁC BẢN LƯU CHỨNG",
    "NO_BASELINE": "KHÔNG CÓ MỐC ĐỂ SO",
}

# Lô, giám định, hồ sơ chốt, tính lại: so với bản đã ghi
RECORDED_LABELS = {
    "UNCHANGED": "KHỚP BẢN ĐÃ GHI",
    "CHANGED": "KHÁC BẢN ĐÃ GHI",
}

ANCHOR_STATUS_LABELS = {
    "PENDING_ANCHOR": "Chờ neo",
    "ANCHORED_UNFINALIZED": "Đã neo, chờ chốt",
    "ANCHORED": "Hoàn chỉnh",
    "ANCHOR_FAILED": "Neo lỗi, đang thử lại",
}

APPRAISAL_STEP_LABELS = {"SEND": "Gửi giám định", "RETURN": "Nhận về sau giám định"}


def vn_time(value: datetime | None) -> str | None:
    """Giờ VN dạng ISO, chính xác tới giây: '2026-11-04T13:12:47+07:00'."""
    return value.astimezone(vietnam_tz).isoformat(timespec="seconds") if value else None


def file_result(value, checked_at: datetime) -> dict:
    """Kết quả so 1 file với bản lưu chứng, kèm 'Kiểm tra lúc' (F5-AC4)."""
    value = getattr(value, "value", value)
    return {"value": value, "label": FILE_LABELS[value], "checkedAt": vn_time(checked_at)}


def recorded_result(value, checked_at: datetime) -> dict:
    """Kết quả so với bản đã ghi (lô, giám định, hồ sơ chốt)."""
    value = getattr(value, "value", value)
    return {"value": value, "label": RECORDED_LABELS[value], "checkedAt": vn_time(checked_at)}
