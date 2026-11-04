import enum


class UserRole(str, enum.Enum):
    PARTY = "PARTY"
    CLERK = "CLERK"
    JUDGE = "JUDGE"
    ADMIN = "ADMIN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    APPEAL = "APPEAL"
    CLOSED = "CLOSED"


class AppealType(str, enum.Enum):
    KHANG_CAO = "KHANG_CAO"
    KHANG_NGHI = "KHANG_NGHI"


class CaseRole(str, enum.Enum):
    PLAINTIFF = "PLAINTIFF"
    DEFENDANT = "DEFENDANT"
    LAWYER = "LAWYER"
    CLERK = "CLERK"
    JUDGE = "JUDGE"


class SubmissionType(str, enum.Enum):
    SELF = "SELF"
    COURT_LOT = "COURT_LOT"


class FileResult(str, enum.Enum):
    """Kết quả so 1 file trong lô với bản lưu chứng (A)."""
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    NO_BASELINE = "NO_BASELINE"


class MatchResult(str, enum.Enum):
    """Kết quả so với bản đã ghi: lô, giám định, hồ sơ chốt, tính lại."""
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"


class AnchorMode(str, enum.Enum):
    PER_SUBMISSION = "PER_SUBMISSION"
    DAILY = "DAILY"


class AnchorResult(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class AnchorStatus(str, enum.Enum):
    """Không lưu DB: suy ra từ Anchor/AnchorLeaf."""
    PENDING_ANCHOR = "PENDING_ANCHOR"
    ANCHORED = "ANCHORED"
    ANCHOR_FAILED = "ANCHOR_FAILED"


class CheckTarget(str, enum.Enum):
    LOT = "LOT"
    FILE = "FILE"
    DOSSIER = "DOSSIER"


class AppraisalStepType(str, enum.Enum):
    SEND = "SEND"
    RETURN = "RETURN"


class AccessResult(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
