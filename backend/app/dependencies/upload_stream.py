"""Kiểm tra file tải lên: số lượng, dung lượng, loại file (chỉ PDF, ảnh, video, âm thanh).

TODO: nhận multipart theo luồng, băm từng chunk, không ghi file ra đĩa. Hiện dùng UploadFile của FastAPI,
file > 1MB có thể được ghi tạm ra đĩa trong lúc xử lý request.
"""
from fastapi import UploadFile

from app.config import settings
from app.core.file_types import check_file
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError


def require_file(file: UploadFile) -> UploadFile:
    limit = settings.max_file_mb * 1024 * 1024
    if file.size is not None and file.size > limit:
        raise AppError(400, ErrorCode.FILE_TOO_LARGE, f"Tệp '{file.filename}' vượt quá {settings.max_file_mb}MB.")
    reason = check_file(file.filename, file.file)
    if reason:
        raise AppError(400, ErrorCode.FILE_TYPE_NOT_ALLOWED, reason)
    return file


def require_files(files: list[UploadFile] | None) -> list[UploadFile]:
    files = [f for f in (files or []) if f.filename]
    if not files:
        raise AppError(400, ErrorCode.FILE_REQUIRED, "Cần ít nhất một tệp trong trường 'files'.")
    if len(files) > settings.max_files_per_submission:
        raise AppError(400, ErrorCode.TOO_MANY_FILES,
                       f"Tối đa {settings.max_files_per_submission} tệp mỗi lần nộp.")
    return [require_file(f) for f in files]
