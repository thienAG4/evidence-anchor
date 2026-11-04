import hashlib
import random
import time
from datetime import datetime, timezone, timedelta
from typing import BinaryIO

# Set up timezone for Vietnam (UTC +7)
vietnam_tz = timezone(timedelta(hours=7))

BUNDLE_SCHEME = "per-file-time-v2"
LOT_SCHEME = "court-lot-v1"
CHUNK_SIZE = 1024 * 1024  # 1MB


def hash_stream(stream: BinaryIO) -> str:
    """Hash 1 luồng nhị phân bằng SHA-256. Đọc từng khúc 1MB để không tốn RAM."""
    h = hashlib.sha256()
    while chunk := stream.read(CHUNK_SIZE):
        h.update(chunk)
    return h.hexdigest()


def hash_file(file_path: str) -> str:
    """Hash the contents of 'a file' using SHA-256."""
    with open(file_path, "rb") as f:
        return hash_stream(f)


def hash_text(text: str) -> str:
    """SHA-256 của 1 chuỗi UTF-8 (dùng cho timestamp)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_concat(*hex_hashes: str) -> str:
    """SHA256(h1 ‖ h2 ‖ ...), với ‖ là nối 32 byte nhị phân của từng hash."""
    return hashlib.sha256(b"".join(bytes.fromhex(h) for h in hex_hashes)).hexdigest()


def now_vn() -> str:
    """Thời điểm hiện tại giờ VN, chính xác tới 1/100 giây: '2026-11-01T14:30:45.37+07:00'."""
    dt = datetime.now(vietnam_tz)
    return f"{dt:%Y-%m-%dT%H:%M:%S}.{dt.microsecond // 10000:02d}+07:00"


def leaf_hash(file_hash: str, hashed_at: str) -> dict:
    """Hti = SHA256(ti), Ha = SHA256(Hi ‖ Hti)."""
    time_hash = hash_text(hashed_at)
    return {"timeHash": time_hash, "leafHash": hash_concat(file_hash, time_hash)}


def hash_evidence(items: list[tuple[str, BinaryIO]], sleep_range=(1.0, 3.0)) -> list[dict]:
    """Hash lần lượt từng file (tên, luồng nhị phân), ghi thời điểm hash xong.

    Giữa 2 file nghỉ ngẫu nhiên 1.00-3.00 giây (2 số lẻ) để mỗi file có mốc thời gian riêng.
    """
    entries = []
    for i, (name, stream) in enumerate(items):
        file_hash = hash_stream(stream)
        hashed_at = now_vn()
        entry = {"fileName": name, "fileHash": file_hash, "hashedAt": hashed_at,
                 **leaf_hash(file_hash, hashed_at)}
        if i < len(items) - 1:
            pause = round(random.uniform(*sleep_range), 2)
            time.sleep(pause)
            entry["sleepAfterSeconds"] = pause
        entries.append(entry)
    return entries


def compute_habc(entries: list[dict]) -> dict:
    """Habc = SHA256(Ha ‖ Hb ‖ Hc ...), các lá sắp theo Hi giảm dần (Z→A)."""
    leaves = [{**e, **leaf_hash(e["fileHash"], e["hashedAt"])} for e in entries]
    leaves.sort(key=lambda e: (e["fileHash"], e["leafHash"]), reverse=True)
    return {
        "order": [e["fileHash"] for e in leaves],
        "habc": hash_concat(*(e["leafHash"] for e in leaves)),
    }


def finalize_bundle(habc: dict, bundled_at: str) -> dict:
    """Bundle = SHA256(Habc ‖ SHA256(thời điểm tính xong Habc))."""
    bundle_time_hash = hash_text(bundled_at)
    return {
        **habc,
        "bundledAt": bundled_at,
        "bundleTimeHash": bundle_time_hash,
        "bundleHash": hash_concat(habc["habc"], bundle_time_hash),
    }


def create_bundle(entries: list[dict]) -> dict:
    """Gộp các file đã hash -> bundle, lấy thời điểm Habc tính xong làm mốc."""
    habc = compute_habc(entries)
    return finalize_bundle(habc, now_vn())


def compute_bundle(entries: list[dict], bundled_at: str) -> dict:
    """Tính lại bundle từ (fileHash, hashedAt) trong biên nhận để kiểm tra."""
    return finalize_bundle(compute_habc(entries), bundled_at)


def lot_meta_hash(place: str, file_count: int) -> str:
    """SHA256("{nơi nộp}|{số lượng}") — đổi nơi hay số lượng là Bundle lô khác."""
    return hash_text(f"{place}|{file_count}")


def finalize_lot_bundle(habc: dict, bundled_at: str, place: str, file_count: int) -> dict:
    """Bundle lô = SHA256(Habc ‖ SHA256(thời điểm gộp) ‖ SHA256(nơi|số lượng))."""
    bundle_time_hash = hash_text(bundled_at)
    meta_hash = lot_meta_hash(place, file_count)
    return {
        **habc,
        "bundledAt": bundled_at,
        "bundleTimeHash": bundle_time_hash,
        "lotMetaHash": meta_hash,
        "bundleHash": hash_concat(habc["habc"], bundle_time_hash, meta_hash),
    }


def create_lot_bundle(entries: list[dict], place: str) -> dict:
    """Hash tổng của lô nộp tại Tòa, lấy thời điểm Habc tính xong làm mốc."""
    return finalize_lot_bundle(compute_habc(entries), now_vn(), place, len(entries))


def compute_lot_bundle(entries: list[dict], bundled_at: str, place: str, file_count: int) -> dict:
    """Tính lại hash tổng lô từ file chọn lại + giờ, nơi, số lượng đọc từ bản ghi lô (F3-AC5)."""
    return finalize_lot_bundle(compute_habc(entries), bundled_at, place, file_count)


def format_vn(iso_time: str) -> str:
    """'2026-11-01T14:30:45.37+07:00' -> '01/11/2026 14:30:45.37'"""
    return f"{iso_time[8:10]}/{iso_time[5:7]}/{iso_time[0:4]} {iso_time[11:22]}"
