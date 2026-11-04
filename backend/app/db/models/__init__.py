"""Import mọi model để Base.metadata đủ bảng (alembic autogenerate)."""
from app.db.models.access_log import AccessLog
from app.db.models.anchor import Anchor, AnchorLeaf
from app.db.models.appraisal import AppraisalStep
from app.db.models.court_case import CaseParticipant, CourtCase
from app.db.models.dossier import Dossier, DossierItem
from app.db.models.submission import FileHash, IntegrityCheck, Submission
from app.db.models.user import User

__all__ = [
    "AccessLog", "Anchor", "AnchorLeaf", "AppraisalStep", "CaseParticipant", "CourtCase",
    "Dossier", "DossierItem", "FileHash", "IntegrityCheck", "Submission", "User",
]
