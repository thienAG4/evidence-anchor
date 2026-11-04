"""POST/GET /cases/{id}/dossiers, POST /dossiers/{id}/checks."""
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db.enums import CaseRole, UserRole
from app.db.models import CourtCase, User
from app.db.session import get_db
from app.dependencies.case_member import case_clerk, case_member, require_case_access
from app.dependencies.roles import require_role
from app.dependencies.upload_stream import require_files
from app.labels import vn_time
from app.services import dossier_service
from app.services.lot_service import check_view

router = APIRouter(tags=["dossiers"])


@router.post("/cases/{case_id}/dossiers", status_code=201)
def create_dossier(files: list[UploadFile] = File([]), doc_names: list[str] = Form([], alias="docNames"),
                   case: CourtCase = Depends(case_clerk), user: User = Depends(require_role(UserRole.CLERK)),
                   db: Session = Depends(get_db)):
    """Chốt hồ sơ trước khi gửi phúc thẩm: docNames[i] là tên tài liệu của files[i]."""
    files = require_files(files)
    dossier = dossier_service.create_dossier(db, case, user, doc_names, [f.file for f in files])
    return {"dossierId": str(dossier.id), "recordedAt": vn_time(dossier.created_at), "createdBy": user.full_name,
            "fileCount": dossier.file_count}


@router.get("/cases/{case_id}/dossiers")
def list_dossiers(case: CourtCase = Depends(case_member(CaseRole.CLERK, CaseRole.JUDGE)),
                  db: Session = Depends(get_db)):
    return {"items": [dossier_service.dossier_view(db, d) for d in dossier_service.list_dossiers(db, case)]}


@router.post("/dossiers/{dossier_id}/checks")
def check_dossier(dossier_id: uuid.UUID, files: list[UploadFile] = File([]),
                  doc_names: list[str] = Form([], alias="docNames"),
                  user: User = Depends(require_role(UserRole.CLERK)), db: Session = Depends(get_db)):
    """Tòa phúc thẩm (thư ký đã được thêm vào vụ) đối chiếu hồ sơ nhận được với bản đã chốt."""
    files = require_files(files)
    dossier = dossier_service.get_dossier(db, dossier_id)
    require_case_access(db, dossier.case_id, user, {CaseRole.CLERK})
    return check_view(dossier_service.check_dossier(db, dossier, user, doc_names, [f.file for f in files]))
