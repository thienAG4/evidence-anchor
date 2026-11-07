"""Trả về { "error": { "code", "message" } } cho mọi lỗi."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors.codes import ErrorCode

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status_code: int, code: ErrorCode, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status_code: int, code: ErrorCode, message: str, details: list | None = None) -> JSONResponse:
    error = {"code": code.value, "message": message}
    if details:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


FIELD_NAMES = {"username": "Tên đăng nhập", "email": "Email", "password": "Mật khẩu", "files": "Tệp",
               "file": "Tệp", "receipt": "Biên nhận", "page": "Số trang", "size": "Số dòng mỗi trang"}
PATTERN_HINTS = {"username": "chỉ gồm chữ không dấu, số và . _ -", "email": "phải có dạng ten@mien.vn"}


def describe_validation_error(err: dict) -> dict:
    """Lỗi kiểm dữ liệu của FastAPI -> {field, reason} tiếng Việt, nói rõ sai gì và sửa thế nào."""
    loc = [p for p in err["loc"] if p not in ("body", "query", "path", "header")]
    field = str(loc[0]) if loc and isinstance(loc[0], str) else None
    name = FIELD_NAMES.get(field, field or "Dữ liệu")
    kind, msg, ctx = err["type"], err.get("msg", ""), err.get("ctx") or {}

    if kind == "json_invalid":
        reason = "Body không phải JSON hợp lệ (kiểm tra dấu ngoặc, dấu phẩy, dấu nháy kép)."
    elif "UploadFile" in msg:
        reason = (f"Chưa đính kèm file ở '{field}': ô này đang chứa chữ gõ tay. Hãy chọn file từ máy "
                  "(Postman: đổi kiểu của key từ Text sang File). Nhận mọi loại file: ảnh, ghi âm, video, PDF, Word...")
    elif kind == "missing":
        reason = f"Thiếu {name.lower()} (trường '{field}')."
    elif kind == "string_pattern_mismatch":
        reason = f"{name} {PATTERN_HINTS.get(field, 'sai định dạng')}."
    elif kind == "string_too_short":
        reason = f"{name} không được để trống."
    elif kind == "string_too_long":
        reason = f"{name} dài quá {ctx.get('max_length')} ký tự."
    elif kind.startswith("int") or kind == "int_parsing":
        reason = f"{name} phải là số nguyên."
    elif kind in ("greater_than_equal", "less_than_equal"):
        sign = "≥" if kind == "greater_than_equal" else "≤"
        reason = f"{name} phải {sign} {ctx.get('ge', ctx.get('le'))}."
    else:
        reason = f"{name} không hợp lệ."
    return {"field": ".".join(str(p) for p in loc) or None, "reason": reason}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            item = describe_validation_error(err)
            if all(d["reason"] != item["reason"] for d in details):  # nhiều file cùng lỗi thì chỉ báo 1 lần
                details.append(item)
        message = " ".join(d["reason"] for d in details)
        return error_response(422, ErrorCode.VALIDATION_ERROR, message, details)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("Lỗi không mong đợi: %s %s", request.method, request.url.path)
        return error_response(500, ErrorCode.INTERNAL_ERROR, "Lỗi hệ thống.")
