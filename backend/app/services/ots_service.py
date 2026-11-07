"""OpenTimestamps phía server (tài liệu kỹ thuật 6.9). Trình duyệt đương sự tự đóng dấu fileHash (server trả trong
biên nhận); server chỉ: chuyển tiếp khi máy chủ lịch chặn CORS, lưu bản chờ, nâng cấp mỗi giờ, báo động sau 48 giờ.

Chỉ áp dụng cho bản ghi A (lưu chứng của đương sự). Đối chiếu với Bitcoin do người kiểm tra tự làm
(opentimestamps.org hoặc `ots verify`); /verify chỉ kiểm offline: .ots đúng hash file và đang chờ hay đã có block.
"""
import base64
import logging
import urllib.request
from datetime import datetime, timedelta, timezone

from opentimestamps.calendar import DEFAULT_CALENDAR_WHITELIST
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import ots
from app.db.enums import SubmissionType
from app.db.models import FileHash, OtsStamp, Submission
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError

logger = logging.getLogger(__name__)
COMPLETE, PENDING = "COMPLETE", "PENDING"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def relay(index: int, digest: bytes) -> bytes:
    """Chuyển tiếp một giá trị băm 32 byte (đã trộn nonce ở trình duyệt) tới máy chủ lịch thứ index."""
    if not 0 <= index < len(settings.ots_calendars) or len(digest) != 32:
        raise AppError(400, ErrorCode.INVALID_OTS, "Cần số thứ tự máy chủ lịch hợp lệ và đúng 32 byte.")
    req = urllib.request.Request(settings.ots_calendars[index].rstrip("/") + "/digest", data=digest,
                                 headers={"Accept": "application/vnd.opentimestamps.v1", "User-Agent": ots.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read(10001)
    except Exception as exc:
        raise AppError(502, ErrorCode.CALENDAR_UNAVAILABLE, f"Máy chủ lịch không trả lời: {exc}") from None
    if len(body) > 10000:
        raise AppError(502, ErrorCode.CALENDAR_UNAVAILABLE, "Máy chủ lịch trả dữ liệu quá lớn.")
    return body


def save_pending(db: Session, submission: Submission, file_code: str, data: bytes) -> OtsStamp:
    """Nhận bản chờ trình duyệt vừa tạo. Kiểm: đọc được, đúng hash của file, chỉ trỏ tới máy chủ lịch cho phép
    (job nâng cấp sẽ gọi các địa chỉ này), chưa có dấu cho file đó."""
    if submission.type != SubmissionType.SELF:
        raise AppError(400, ErrorCode.INVALID_OTS, "Chỉ đóng dấu OpenTimestamps cho lưu chứng của đương sự (bước A).")
    file = db.scalar(select(FileHash).where(FileHash.submission_id == submission.id,
                                            FileHash.file_code == file_code.strip().upper()))
    if file is None:
        raise AppError(404, ErrorCode.FILE_CODE_NOT_FOUND, f"Biên nhận không có mã file {file_code}.")
    try:
        meta = ots.info(data)
    except ots.OtsError as exc:
        raise AppError(400, ErrorCode.INVALID_OTS, str(exc)) from None
    if meta.file_hash != file.file_hash:
        raise AppError(400, ErrorCode.INVALID_OTS, "File .ots không đóng dấu đúng hash của file này.")
    if not meta.pending_calendars or any(uri not in DEFAULT_CALENDAR_WHITELIST for uri in meta.pending_calendars):
        raise AppError(400, ErrorCode.INVALID_OTS, "File .ots phải chờ ở máy chủ lịch OpenTimestamps được cho phép.")
    if db.scalar(select(OtsStamp.id).where(OtsStamp.record_seq == file.record_seq)):
        raise AppError(409, ErrorCode.OTS_EXISTS, f"{file.file_code} đã có dấu OpenTimestamps.")
    stamp = OtsStamp(record_seq=file.record_seq, file_hash=file.file_hash, ots_pending=data, stamped_at=_now())
    db.add(stamp)
    db.commit()
    return stamp


def upgrade_pending(db: Session, now: datetime | None = None, upgrade=ots.upgrade) -> dict:
    """Job mỗi giờ: nâng cấp mọi bản chờ; quá ots_alarm_hours chưa xong thì báo động (log ERROR)."""
    now = now or _now()
    done = waiting = late = 0
    for stamp in db.scalars(select(OtsStamp).where(OtsStamp.ots_complete.is_(None)).order_by(OtsStamp.stamped_at)):
        try:
            data, complete = upgrade(stamp.ots_pending)
        except Exception as exc:  # mất mạng, máy chủ lịch lỗi: lần sau thử lại
            logger.warning("Nâng cấp .ots bản ghi %s lỗi: %s", stamp.record_seq, exc)
            complete = False
        if complete:
            stamp.ots_complete, stamp.upgraded_at = data, now
            stamp.bitcoin_block = min(ots.info(data).bitcoin_blocks)
            db.commit()
            done += 1
            logger.info("OpenTimestamps bản ghi %s: đã có trên Bitcoin block %s", stamp.record_seq, stamp.bitcoin_block)
            continue
        waiting += 1
        if now - stamp.stamped_at > timedelta(hours=settings.ots_alarm_hours):
            late += 1
            logger.error("OpenTimestamps bản ghi %s chưa xác nhận sau %s giờ (đóng dấu lúc %s)", stamp.record_seq,
                         settings.ots_alarm_hours, stamp.stamped_at.isoformat())
    return {"upgraded": done, "pending": waiting, "late": late}


def view(db: Session, submission: Submission) -> list[dict]:
    """Phần OpenTimestamps của biên nhận: mỗi file đã đóng dấu một mục, bản hoàn chỉnh nếu có, không thì bản chờ."""
    files = list(db.scalars(select(FileHash).where(FileHash.submission_id == submission.id).order_by(FileHash.position)))
    stamps = {s.record_seq: s for s in db.scalars(select(OtsStamp).where(
        OtsStamp.record_seq.in_([f.record_seq for f in files])))}
    items = []
    for f in files:
        s = stamps.get(f.record_seq)
        if s is None:
            continue
        items.append({
            "fileCode": f.file_code, "status": COMPLETE if s.ots_complete else PENDING,
            "bitcoinBlock": s.bitcoin_block, "stampedAt": s.stamped_at.isoformat(),
            "ots": base64.b64encode(s.ots_complete or s.ots_pending).decode(),
        })
    return items
