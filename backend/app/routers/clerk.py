"""Giao diện thư ký: các lần lưu chứng cứ của đương sự trong vụ mình phụ trách, đối chiếu từng file."""
import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db.enums import UserRole
from app.db.models import User
from app.db.session import get_db
from app.dependencies.roles import require_role
from app.dependencies.upload_stream import require_file, require_files
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError
from app.labels import DISCLAIMER, file_result
from app.services import receipt_service

router = APIRouter(prefix="/clerk", tags=["clerk"])
clerk_only = require_role(UserRole.CLERK)


@router.get("/receipts")
def list_receipts(user: User = Depends(clerk_only), db: Session = Depends(get_db)):
    """Không có mã hash: thư ký chỉ thấy mã file, tên file, giờ, người lưu, kết quả."""
    return {"items": [receipt_service.receipt_view(db, s) for s in receipt_service.receipts_for_clerk(db, user)]}


@router.get("/receipts/{code}")
def get_receipt(code: str, user: User = Depends(clerk_only), db: Session = Depends(get_db)):
    return receipt_service.receipt_view(db, receipt_service.receipt_for_clerk(db, user, code))


@router.post("/receipts/{code}/compare")
def compare_file(code: str, file_code: str = Form(..., alias="fileCode"), file: UploadFile = File(...),
                 user: User = Depends(clerk_only), db: Session = Depends(get_db)):
    """Xem trước: so 1 file trong hồ sơ Tòa với file cùng mã trong biên nhận. Không ghi kết quả."""
    submission = receipt_service.receipt_for_clerk(db, user, code)
    result = receipt_service.compare(db, submission, file_code, require_file(file).file)
    return {"fileCode": file_code.strip().upper(), "value": result.value,
            "label": file_result(result, None)["label"], "disclaimer": DISCLAIMER}


@router.post("/receipts/{code}/verifications", status_code=201)
def save_verification(code: str, phase: str = Form(..., min_length=1, max_length=100),
                      meta: str = Form(...), files: list[UploadFile] = File([]),
                      user: User = Depends(clerk_only), db: Session = Depends(get_db)):
    """Lưu kết quả đối chiếu. meta: JSON [{"fileCode": "TX-0001-1"}, ...] cùng thứ tự files[]."""
    files = require_files(files)
    try:
        codes = [item["fileCode"] for item in json.loads(meta)]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise AppError(400, ErrorCode.META_MISMATCH, 'meta phải là JSON dạng [{"fileCode": "TX-0001-1"}]') from None
    if len(codes) != len(files):
        raise AppError(400, ErrorCode.META_MISMATCH, f"meta có {len(codes)} mã nhưng gửi {len(files)} file.")
    submission = receipt_service.receipt_for_clerk(db, user, code)
    saved = receipt_service.save_verification(db, user, submission, phase, list(zip(codes, [f.file for f in files])))
    return {"receiptCode": submission.receipt_code, "phase": phase,
            "results": [{"fileCode": t.file_code, "result": file_result(c.result, c.checked_at)} for t, c in saved],
            "disclaimer": DISCLAIMER}


@router.get("/litigants")
def list_litigants(user: User = Depends(clerk_only), db: Session = Depends(get_db)):
    """Đương sự trong các vụ mình làm thư ký, kèm số lần lưu chứng, số file, lần gần nhất."""
    return {"items": receipt_service.litigants_for_clerk(db, user)}
