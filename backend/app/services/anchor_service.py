"""Chọn bản ghi chưa neo, gửi giao dịch, ghi Anchor + AnchorLeaf (chỉ ghi thêm); suy ra trạng thái neo."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.enums import AnchorMode, AnchorResult, AnchorStatus
from app.db.models import Anchor, AnchorLeaf, Submission

logger = logging.getLogger(__name__)
EXPLORER_TX_URL = "https://sepolia.etherscan.io/tx/"


def anchor_state(db: Session, submission_id) -> tuple[AnchorStatus, Anchor | None, AnchorLeaf | None]:
    """ANCHORED nếu có lần neo CONFIRMED; ANCHOR_FAILED nếu mọi lần neo đều lỗi; chưa có lần nào: PENDING_ANCHOR."""
    rows = db.execute(
        select(AnchorLeaf, Anchor).join(Anchor, AnchorLeaf.anchor_id == Anchor.id)
        .where(AnchorLeaf.submission_id == submission_id).order_by(Anchor.created_at.desc())
    ).all()
    for leaf, anchor in rows:
        if anchor.result == AnchorResult.CONFIRMED:
            return AnchorStatus.ANCHORED, anchor, leaf
    if rows:
        return AnchorStatus.ANCHOR_FAILED, rows[0][1], rows[0][0]
    return AnchorStatus.PENDING_ANCHOR, None, None


def anchor_view(anchor: Anchor, leaf: AnchorLeaf) -> dict:
    """Phần thêm vào biên nhận hoàn chỉnh khi đã neo (F1-AC5)."""
    return {
        "mode": anchor.mode.value,
        "rootHash": anchor.root_hash,
        "leafIndex": leaf.leaf_index,
        "merkleProof": leaf.merkle_proof,
        "txHash": anchor.tx_hash,
        "blockNumber": anchor.block_number,
        "blockTime": anchor.block_time.isoformat() if anchor.block_time else None,
        "explorerUrl": EXPLORER_TX_URL + anchor.tx_hash if anchor.tx_hash else None,
    }


def submissions_to_anchor(db: Session, limit: int = 20) -> list[Submission]:
    """Chưa có lần neo CONFIRMED, và lần lỗi gần nhất đã cách đủ anchor_retry_seconds."""
    confirmed = (select(AnchorLeaf.submission_id).join(Anchor, AnchorLeaf.anchor_id == Anchor.id)
                 .where(Anchor.result == AnchorResult.CONFIRMED))
    retry_after = datetime.now(timezone.utc) - timedelta(seconds=settings.anchor_retry_seconds)
    recently_failed = (select(AnchorLeaf.submission_id).join(Anchor, AnchorLeaf.anchor_id == Anchor.id)
                       .where(Anchor.result == AnchorResult.FAILED, Anchor.created_at > retry_after))
    return list(db.scalars(
        select(Submission).where(Submission.id.not_in(confirmed), Submission.id.not_in(recently_failed))
        .order_by(Submission.submitted_at).limit(limit)
    ))


def anchor_submission(db: Session, chain, submission: Submission) -> Anchor:
    """Chế độ per_submission: 1 giao dịch chứa bundle_hash, cây Merkle 1 lá (gốc = lá, đường dẫn rỗng)."""
    anchor = Anchor(mode=AnchorMode.PER_SUBMISSION, root_hash=submission.bundle_hash, leaf_count=1)
    try:
        tx = chain.anchor_to_sepolia(submission.bundle_hash)
        anchor.result = AnchorResult.CONFIRMED
        anchor.tx_hash = tx["txHash"]
        anchor.block_number = tx["blockNumber"]
        anchor.block_time = datetime.fromtimestamp(tx["blockTimestampUnix"], tz=timezone.utc)
    except Exception as exc:  # mọi lỗi RPC/giao dịch đều ghi FAILED để thử lại sau
        logger.warning("Neo %s lỗi: %s", submission.receipt_code, exc)
        anchor.result = AnchorResult.FAILED
        anchor.error = str(exc)[:1000]
    db.add(anchor)
    db.flush()
    db.add(AnchorLeaf(anchor_id=anchor.id, submission_id=submission.id, leaf_index=0, merkle_proof=[]))
    db.commit()
    return anchor
