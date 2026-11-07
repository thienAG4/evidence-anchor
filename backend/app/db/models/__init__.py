"""Import mọi model để Base.metadata đủ bảng (alembic autogenerate)."""
from app.db.models.access_log import AccessLog
from app.db.models.anchor import AnchorBatch, AnchorLeaf, AnchorState, ChainTx, ChainTxResult
from app.db.models.appraisal import AppraisalStep
from app.db.models.court_case import CaseParticipant, CourtCase
from app.db.models.dossier import Dossier, DossierItem
from app.db.models.log_record import LogRecord
from app.db.models.ots import OtsStamp
from app.db.models.submission import FileHash, IntegrityCheck, Submission
from app.db.models.user import User

__all__ = [
    "AccessLog", "AnchorBatch", "AnchorLeaf", "AnchorState", "AppraisalStep", "CaseParticipant", "ChainTx",
    "ChainTxResult", "CourtCase",
    "Dossier", "DossierItem", "FileHash", "IntegrityCheck", "LogRecord", "OtsStamp", "Submission", "User",
]
