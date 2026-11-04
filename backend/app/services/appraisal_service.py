"""Giám định (F4): thư ký ghi thay bước gửi đi / nhận về; so với hash đã ghi lúc nhận (E), không so với A."""
from datetime import datetime, timezone
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.hashing import hash_stream
from app.db.enums import AppraisalStepType, MatchResult
from app.db.models import AppraisalStep, FileHash, User
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError
from app.labels import APPRAISAL_STEP_LABELS, DISCLAIMER, recorded_result, vn_time


def steps_of(db: Session, evidence: FileHash) -> list[AppraisalStep]:
    return list(db.scalars(select(AppraisalStep).where(AppraisalStep.file_id == evidence.id)
                           .order_by(AppraisalStep.recorded_at)))


def record_step(db: Session, evidence: FileHash, clerk: User, step: AppraisalStepType,
                stream: BinaryIO) -> AppraisalStep:
    file_hash = hash_stream(stream)
    result = MatchResult.UNCHANGED if file_hash == evidence.file_hash else MatchResult.CHANGED
    steps = steps_of(db, evidence)
    last = steps[-1] if steps else None
    if step == AppraisalStepType.SEND:
        if last is not None and last.step == AppraisalStepType.SEND:
            raise AppError(409, ErrorCode.INVALID_STATE, "Chứng cứ đang ở chỗ giám định, chưa ghi nhận về.")
        if result == MatchResult.CHANGED:  # F4-AC1
            raise AppError(409, ErrorCode.FILE_CHANGED_SINCE_RECEIPT,
                           "File khác bản đã ghi lúc nhận, không gửi giám định được.")
    elif last is None or last.step != AppraisalStepType.SEND:
        raise AppError(409, ErrorCode.INVALID_STATE, "Chưa ghi bước gửi giám định nên chưa nhận về được.")
    record = AppraisalStep(file_id=evidence.id, step=step, file_hash=file_hash, result=result,
                           recorded_by=clerk.id, recorded_at=datetime.now(timezone.utc))
    db.add(record)  # RETURN mà khác E vẫn ghi: KHÁC BẢN ĐÃ GHI, biết khác ở bước nào (F4-AC2)
    db.commit()
    return record


def step_view(db: Session, record: AppraisalStep) -> dict:
    recorder = db.get(User, record.recorded_by)
    return {"step": record.step.value, "stepLabel": APPRAISAL_STEP_LABELS[record.step.value],
            "result": recorded_result(record.result, record.recorded_at), "recordedAt": vn_time(record.recorded_at),
            "recordedBy": recorder.full_name if recorder else None, "disclaimer": DISCLAIMER}
