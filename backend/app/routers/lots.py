"""Lô tại Tòa và chứng cứ: /baselines/{fileCode}, /cases/{id}/lots..., /cases/{id}/evidence/{fid}/..."""
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db.enums import AppraisalStepType, CaseRole, UserRole
from app.db.models import CourtCase, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.case_member import PARTY_CASE_ROLES, case_clerk, case_member
from app.dependencies.roles import require_role
from app.dependencies.upload_stream import require_file, require_files
from app.services import appraisal_service, lot_service

router = APIRouter(tags=["lots"])
any_member = case_member(*PARTY_CASE_ROLES, CaseRole.CLERK, CaseRole.JUDGE)


@router.get("/baselines/{file_code}")
def get_baseline(file_code: str, user: User = Depends(require_role(UserRole.CLERK)), db: Session = Depends(get_db)):
    """Giờ lưu chứng + người lưu của mã file; không có file, không có hash."""
    return lot_service.baseline_view(db, file_code)


@router.post("/cases/{case_id}/lots", status_code=202)
def create_lot(files: list[UploadFile] = File([]), place: str | None = Form(None), meta: str | None = Form(None),
               case: CourtCase = Depends(case_clerk), user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Thư ký nạp file đương sự nộp tại Tòa. meta: JSON [{"fileCode": "TX-0001-1"}, {"fileCode": ""}] cùng thứ tự files.

    place trống thì lấy tòa của thư ký.
    """
    files = require_files(files)
    codes = lot_service.parse_meta(meta, len(files))
    lot = lot_service.create_lot(db, case, user, place, codes, [(f.filename, f.file) for f in files])
    view = lot_service.lot_view(db, lot, show_baseline=True)
    return {k: view[k] for k in ("lotId", "receiptCode", "lotNo", "receivedAt", "place", "fileCount",
                                 "anchorStatus", "result", "disclaimer")} | {
        "files": [{"evidenceId": f["evidenceId"], "fileName": f["fileName"], "result": f["result"]}
                  for f in view["files"]]}


@router.get("/cases/{case_id}/lots")
def list_lots(case: CourtCase = Depends(any_member), user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """Kết quả từng lô và từng chứng cứ (F5) cho người trong vụ."""
    show = user.role == UserRole.CLERK
    return {"caseNumber": case.case_number,
            "items": [lot_service.lot_view(db, lot, show) for lot in lot_service.list_lots(db, case)]}


@router.get("/cases/{case_id}/lots/{lot_id}")
def get_lot(lot_id: uuid.UUID, case: CourtCase = Depends(any_member), user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    return lot_service.lot_view(db, lot_service.get_lot(db, case, lot_id), user.role == UserRole.CLERK)


@router.post("/cases/{case_id}/lots/{lot_id}/checks")
def recheck_lot(lot_id: uuid.UUID, files: list[UploadFile] = File([]), case: CourtCase = Depends(case_clerk),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tính lại hash tổng từ file thư ký chọn lại trong hồ sơ Tòa (F3-AC5)."""
    files = require_files(files)
    lot = lot_service.get_lot(db, case, lot_id)
    return lot_service.check_view(lot_service.recheck_lot(db, lot, user, [f.file for f in files]))


@router.post("/cases/{case_id}/evidence/{evidence_id}/checks")
def recheck_evidence(evidence_id: uuid.UUID, file: UploadFile = File(...), case: CourtCase = Depends(case_clerk),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """So 1 chứng cứ chọn lại với bản đã ghi lúc nhận."""
    evidence = lot_service.get_evidence(db, case, evidence_id)
    return lot_service.check_view(lot_service.recheck_evidence(db, evidence, user, require_file(file).file))


@router.post("/cases/{case_id}/evidence/{evidence_id}/appraisal-steps", status_code=201)
def record_appraisal_step(evidence_id: uuid.UUID, step: AppraisalStepType = Form(...), file: UploadFile = File(...),
                          case: CourtCase = Depends(case_clerk), user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """Thư ký ghi thay người giám định: SEND (gửi đi) / RETURN (nhận về)."""
    evidence = lot_service.get_evidence(db, case, evidence_id)
    return appraisal_service.step_view(
        db, appraisal_service.record_step(db, evidence, user, step, require_file(file).file))


@router.get("/cases/{case_id}/evidence/{evidence_id}/appraisal-steps")
def list_appraisal_steps(evidence_id: uuid.UUID, case: CourtCase = Depends(any_member),
                         db: Session = Depends(get_db)):
    evidence = lot_service.get_evidence(db, case, evidence_id)
    return {"evidenceId": str(evidence.id), "fileName": evidence.file_name,
            "items": [appraisal_service.step_view(db, s) for s in appraisal_service.steps_of(db, evidence)]}
