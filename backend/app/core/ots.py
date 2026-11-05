"""OpenTimestamps (tài liệu kỹ thuật 6.9): chứng minh hash file đã tồn tại trước một block Bitcoin.

Máy chủ lịch chỉ nhận một giá trị băm: SHA256(fileHash ‖ nonce 16 byte ngẫu nhiên), không thấy file, cũng không thấy
fileHash. File .ots mới tạo ở trạng thái chờ (PendingAttestation); sau khi Bitcoin xác nhận (thường vài giờ) thì
nâng cấp thành bản hoàn chỉnh (BitcoinBlockHeaderAttestation). Bản chờ gửi tới nhiều máy chủ lịch để đương sự tự
nâng cấp được dù máy chủ Tòa ngừng hoạt động: `ots upgrade file.ots`, rồi `ots verify` hoặc opentimestamps.org.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.serialize import BytesDeserializationContext, BytesSerializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

USER_AGENT = "EvidenceChain"


class OtsError(ValueError):
    """File .ots hỏng hoặc không đóng dấu được."""


@dataclass(frozen=True)
class OtsInfo:
    file_hash: str
    pending_calendars: tuple[str, ...]
    bitcoin_blocks: tuple[int, ...]

    @property
    def complete(self) -> bool:
        return bool(self.bitcoin_blocks)


def _serialize(stamp: DetachedTimestampFile) -> bytes:
    ctx = BytesSerializationContext()
    stamp.serialize(ctx)
    return ctx.getbytes()


def _load(ots: bytes) -> DetachedTimestampFile:
    try:
        stamp = DetachedTimestampFile.deserialize(BytesDeserializationContext(ots))
    except Exception as exc:  # thư viện ném nhiều kiểu lỗi khác nhau khi file hỏng
        raise OtsError(f"File .ots không đọc được: {exc}") from None
    if not isinstance(stamp.file_hash_op, OpSHA256):
        raise OtsError("File .ots không dùng SHA-256.")
    return stamp


def _walk(timestamp: Timestamp):
    yield timestamp
    for sub in timestamp.ops.values():
        yield from _walk(sub)


def stamp(file_hash: str, calendars: list[str], timeout: float = 10) -> tuple[bytes, list[str]]:
    """Đóng dấu fileHash (hex). Trả (.ots bản chờ, các máy chủ lịch đã nhận). Không máy chủ nào nhận -> OtsError."""
    detached = DetachedTimestampFile(OpSHA256(), Timestamp(bytes.fromhex(file_hash)))
    tip = detached.timestamp.ops.add(OpAppend(os.urandom(16))).ops.add(OpSHA256())

    def submit(url):
        try:
            return url, RemoteCalendar(url, USER_AGENT).submit(tip.msg, timeout=timeout)
        except Exception:
            return url, None

    with ThreadPoolExecutor(max_workers=len(calendars) or 1) as pool:
        results = list(pool.map(submit, calendars))
    accepted = [url for url, ts in results if ts is not None]
    if not accepted:
        raise OtsError("Không máy chủ lịch OpenTimestamps nào nhận (mất mạng?).")
    for _, ts in results:
        if ts is not None:
            tip.merge(ts)
    return _serialize(detached), accepted


def upgrade(ots: bytes, timeout: float = 10) -> tuple[bytes, bool]:
    """Hỏi lại các máy chủ lịch trong file. Trả (.ots sau khi gộp, đã có block Bitcoin chưa)."""
    detached = _load(ots)
    for ts in list(_walk(detached.timestamp)):
        for att in [a for a in ts.attestations if isinstance(a, PendingAttestation)]:
            try:
                ts.merge(RemoteCalendar(att.uri, USER_AGENT).get_timestamp(ts.msg, timeout=timeout))
            except Exception:
                continue  # máy chủ này chưa có (chưa lên Bitcoin) hoặc tạm lỗi: lần sau hỏi lại
    data = _serialize(detached)
    return data, info(data).complete


def info(ots: bytes) -> OtsInfo:
    detached = _load(ots)
    attestations = [a for _, a in detached.timestamp.all_attestations()]
    return OtsInfo(
        file_hash=detached.file_digest.hex(),
        pending_calendars=tuple(sorted({a.uri for a in attestations if isinstance(a, PendingAttestation)})),
        bitcoin_blocks=tuple(sorted({a.height for a in attestations if isinstance(a, BitcoinBlockHeaderAttestation)})),
    )
