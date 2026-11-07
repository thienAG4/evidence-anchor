"""Chốt hồ sơ khi kháng cáo (F9): hash danh mục + từng file -> bản ghi chốt D; phúc thẩm đối chiếu với D."""
import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.hashing import hash_stream, hash_text
from app.core.log_record import EVENT_D, EVENT_E
from app.db.enums import CaseStatus, CheckTarget, MatchResult
from app.db.models import CourtCase, Dossier, DossierItem, IntegrityCheck, User
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError
from app.labels import DISCLAIMER, recorded_result, vn_time
from app.services.log_service import append_record, result_code, unix_seconds


def catalog_hash(doc_names: list[str], file_hashes: list[str]) -> str:
    """SHA256 của các dòng "{thứ tự}|{tên tài liệu}|{hash file}" nối bằng xuống dòng (docs/entities.md)."""
    return hash_text("\n".join(f"{i}|{name}|{h}" for i, (name, h) in enumerate(zip(doc_names, file_hashes), 1)))


def _check_names(doc_names: list[str], file_count: int) -> list[str]:
    names = [n.strip() for n in doc_names]
    if len(names) != file_count or not all(names):
        raise AppError(400, ErrorCode.META_MISMATCH,
                       f"Cần đúng {file_count} tên tài liệu (docNames) không trống, cùng thứ tự với files.")
    return names


def create_dossier(db: Session, case: CourtCase, clerk: User, doc_names: list[str],
                   streams: list[BinaryIO]) -> Dossier:
    if case.status != CaseStatus.APPEAL or case.appeal_type is None:  # F9-AC1
        raise AppError(409, ErrorCode.APPEAL_REQUIRED, "Chỉ chốt hồ sơ khi vụ đang có kháng cáo hoặc kháng nghị.")
    names = _check_names(doc_names, len(streams))
    hashes = [hash_stream(s) for s in streams]
    catalog, created_at = catalog_hash(names, hashes), datetime.now(timezone.utc)
    # D không phải phép so nên result = 0 như A
    record = append_record(db, event_type=EVENT_D, file_hash=catalog, actor_id=clerk.id,
                           ts=unix_seconds(created_at), case_id=case.id)
    dossier = Dossier(case_id=case.id, appeal_type=case.appeal_type, catalog_hash=catalog, file_count=len(hashes),
                      created_by=clerk.id, created_at=created_at, record_seq=record.seq)
    db.add(dossier)
    db.flush()
    for i, (name, h) in enumerate(zip(names, hashes), 1):
        db.add(DossierItem(dossier_id=dossier.id, position=i, doc_name=name[:255], file_hash=h))
    db.commit()
    return dossier


def get_dossier(db: Session, dossier_id: uuid.UUID) -> Dossier:
    dossier = db.get(Dossier, dossier_id)
    if dossier is None:
        raise AppError(404, ErrorCode.DOSSIER_NOT_FOUND, "Không tìm thấy hồ sơ chốt.")
    return dossier


def check_dossier(db: Session, dossier: Dossier, clerk: User, doc_names: list[str],
                  streams: list[BinaryIO]) -> IntegrityCheck:
    """F9-AC3: thêm, bớt, sửa file hay đổi danh mục -> KHÁC BẢN ĐÃ GHI."""
    names = _check_names(doc_names, len(streams))
    recomputed = catalog_hash(names, [hash_stream(s) for s in streams])
    result = MatchResult.UNCHANGED if recomputed == dossier.catalog_hash else MatchResult.CHANGED
    checked_at = datetime.now(timezone.utc)
    record = append_record(db, event_type=EVENT_E, file_hash=recomputed, actor_id=clerk.id,
                           ts=unix_seconds(checked_at), result=result_code(result), case_id=dossier.case_id,
                           ref_seq=dossier.record_seq)  # E trỏ D
    check = IntegrityCheck(target=CheckTarget.DOSSIER, dossier_id=dossier.id, result=result,
                           checked_by=clerk.id, checked_at=checked_at, record_seq=record.seq)
    db.add(check)
    db.commit()
    return check


def list_dossiers(db: Session, case: CourtCase) -> list[Dossier]:
    return list(db.scalars(select(Dossier).where(Dossier.case_id == case.id).order_by(Dossier.created_at)))


def dossier_view(db: Session, dossier: Dossier) -> dict:
    creator = db.get(User, dossier.created_by)
    last = db.scalar(select(IntegrityCheck).where(IntegrityCheck.dossier_id == dossier.id)
                     .order_by(IntegrityCheck.checked_at.desc()).limit(1))
    items = db.scalars(select(DossierItem).where(DossierItem.dossier_id == dossier.id).order_by(DossierItem.position))
    return {
        "dossierId": str(dossier.id), "appealType": dossier.appeal_type.value, "fileCount": dossier.file_count,
        "recordedAt": vn_time(dossier.created_at), "createdBy": creator.full_name if creator else None,
        "documents": [{"position": i.position, "docName": i.doc_name} for i in items],
        "lastCheck": recorded_result(last.result, last.checked_at) if last else None, "disclaimer": DISCLAIMER,
    }
