"""POST/GET /submissions, POST /submissions/lookup, GET /receipts/{code}, GET /signing-key."""
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.receipt import SIGNATURE_ALGORITHM, signing_address
from app.db.enums import UserRole
from app.db.models import Submission, User
from app.db.session import get_db
from app.dependencies.roles import require_role
from app.dependencies.upload_stream import require_file, require_files
from app.labels import ANCHOR_STATUS_LABELS
from app.services import receipt_service, submission_service
from app.services.anchor_service import anchor_state, anchor_view

router = APIRouter(tags=["submissions"])
party_only = require_role(UserRole.PARTY)


def status_fields(db: Session, submission: Submission) -> dict:
    status, _ = anchor_state(db, submission.id)
    return {"status": status.value, "statusLabel": ANCHOR_STATUS_LABELS[status.value]}


@router.post("/submissions", status_code=202)
def create_submission(files: list[UploadFile] = File([]), user: User = Depends(party_only),
                      db: Session = Depends(get_db)):
    """Lưu chứng: server băm từng file rồi bỏ, trả biên nhận tạm. Worker neo lên Sepolia sau.

    `files` mặc định [] thay vì `| None`: schema "hoặc null" làm Swagger UI (/docs) mất nút chọn file.
    """
    files = require_files(files)
    submission = submission_service.create_self_submission(db, user, [(f.filename, f.file) for f in files])
    receipt = submission.receipt_json
    return {
        "receiptCode": submission.receipt_code,
        **status_fields(db, submission),
        "submittedAt": receipt["submittedAt"],
        "files": [{"fileName": f["fileName"], "fileCode": f["fileCode"], "hashedAt": f["hashedAt"]}
                  for f in receipt["files"]],
    }


@router.get("/submissions")
def list_submissions(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                     user: User = Depends(party_only), db: Session = Depends(get_db)):
    """Biên nhận của mình, kèm kết quả Tòa đối chiếu từng file (nếu có)."""
    rows, total = submission_service.list_own(db, user, page, size)
    return {"page": page, "size": size, "total": total,
            "items": [receipt_service.receipt_view(db, s) for s in rows]}


@router.post("/submissions/lookup")
def lookup(file: UploadFile = File(...), user: User = Depends(party_only), db: Session = Depends(get_db)):
    """Đưa lại file -> tìm bản lưu chứng của chính mình (không cần nhập mã)."""
    file_hash, submission = submission_service.lookup_by_file(db, user, require_file(file).file)
    return {"receiptCode": submission.receipt_code, "fileCode": file_hash.file_code,
            "fileName": file_hash.file_name, "hashedAt": file_hash.hashed_at}


@router.get("/receipts/{code}")
def get_receipt(code: str, user: User = Depends(party_only), db: Session = Depends(get_db)):
    """Biên nhận tạm có chữ ký; đã neo thì có thêm anchor (bản ghi 164 byte từng file, đường dẫn Merkle, txHash)
    để tự kiểm tra.

    receipt + signature + anchor: tải về đưa vào POST /verify. view: dữ liệu cho giao diện (kết quả Tòa đối chiếu).
    """
    submission = submission_service.get_own_by_code(db, user, code)
    status, _ = anchor_state(db, submission.id)
    return {
        "status": status.value,
        "statusLabel": ANCHOR_STATUS_LABELS[status.value],
        "receipt": submission.receipt_json,
        "signature": submission.signature,
        "anchor": anchor_view(db, submission) if status.value == "ANCHORED" else None,
        "view": receipt_service.receipt_view(db, submission, include_hashes=True),
    }


@router.get("/signing-key")
def signing_key():
    """Địa chỉ khóa ký để tự kiểm chữ ký biên nhận (EIP-191: khôi phục địa chỉ từ chữ ký rồi so)."""
    return {"algorithm": SIGNATURE_ALGORITHM, "keyNo": settings.receipt_key_no,
            "address": settings.receipt_signer_address or signing_address()}
