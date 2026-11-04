"""POST /verify (công khai): kiểm tra tệp + biên nhận."""
import json

from fastapi import APIRouter, File, UploadFile

from app.dependencies.upload_stream import require_files
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError
from app.services import verify_service

router = APIRouter(tags=["verify"])


@router.post("/verify")
def verify(receipt: UploadFile = File(...), files: list[UploadFile] = File([])):
    """receipt: file JSON tải từ GET /receipts/{code}; files: các file gốc (đổi tên, đổi thứ tự không sao)."""
    files = require_files(files)
    try:
        document = json.loads(receipt.file.read().decode("utf-8"))
        if not isinstance(document, dict):
            raise ValueError("phải là một đối tượng JSON")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise AppError(400, ErrorCode.INVALID_RECEIPT_FORMAT, f"Không đọc được biên nhận: {exc}") from None
    return verify_service.verify(document, [f.file for f in files])
