"""Loại file được nhận làm chứng cứ: PDF, ảnh, video, âm thanh.

Kiểm cả đuôi file lẫn chữ ký đầu file (magic bytes): đổi tên virus.exe thành anh.jpg vẫn bị chặn.
"""
from pathlib import Path
from typing import BinaryIO

CATEGORIES = {
    "PDF": ("pdf",),
    "ảnh": ("jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "heic", "heif"),
    "video": ("mp4", "mov", "m4v", "avi", "mkv", "webm", "3gp"),
    "âm thanh": ("mp3", "m4a", "wav", "aac", "ogg", "oga", "opus", "flac", "amr"),
}
ALLOWED_EXTENSIONS = tuple(ext for exts in CATEGORIES.values() for ext in exts)
ALLOWED_TEXT = "PDF, ảnh (JPG, PNG, HEIC...), video (MP4, MOV, AVI...), âm thanh (MP3, M4A, WAV...)"
KIND = {ext: kind for kind, exts in CATEGORIES.items() for ext in exts}

QUICKTIME_ATOMS = (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip")  # .mov đời cũ không mở đầu bằng ftyp


def _content_matches(ext: str, head: bytes) -> bool:
    riff_type = head[8:12] if head[:4] == b"RIFF" else b""
    if ext == "pdf":
        return head.startswith(b"%PDF")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "gif":
        return head[:6] in (b"GIF87a", b"GIF89a")
    if ext == "webp":
        return riff_type == b"WEBP"
    if ext == "bmp":
        return head.startswith(b"BM")
    if ext in ("tif", "tiff"):
        return head[:4] in (b"II*\x00", b"MM\x00*")
    if ext == "mov":
        return head[4:8] in QUICKTIME_ATOMS
    if ext in ("mp4", "m4v", "3gp", "m4a", "heic", "heif"):  # họ ISO media: "ftyp" ở byte 4
        return head[4:8] == b"ftyp"
    if ext == "avi":
        return riff_type == b"AVI "
    if ext == "wav":
        return riff_type == b"WAVE"
    if ext in ("mkv", "webm"):
        return head.startswith(b"\x1a\x45\xdf\xa3")
    if ext == "mp3":
        return head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)
    if ext == "aac":
        return head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xF6 == 0xF0)
    if ext in ("ogg", "oga", "opus"):
        return head.startswith(b"OggS")
    if ext == "flac":
        return head.startswith(b"fLaC")
    if ext == "amr":
        return head.startswith(b"#!AMR")
    return False


def check_file(filename: str, stream: BinaryIO) -> str | None:
    """Trả về lý do từ chối (tiếng Việt), hoặc None nếu file được nhận. Đọc 16 byte đầu rồi tua lại."""
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext not in KIND:
        shown = f".{ext}" if ext else "không có đuôi"
        return f"Tệp '{filename}' ({shown}) không được nhận. Chỉ nhận {ALLOWED_TEXT}."
    head = stream.read(16)
    stream.seek(0)
    if not _content_matches(ext, head):
        return (f"Tệp '{filename}' có đuôi .{ext} nhưng nội dung không phải {KIND[ext]} .{ext} thật "
                "(có thể là file khác bị đổi tên).")
    return None
