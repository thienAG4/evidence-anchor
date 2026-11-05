"""Neo LogRecord theo đợt: chốt đợt (AnchorBatch + AnchorLeaf, cấp nonce) -> ký, ghi ChainTx -> phát lên mạng ->
theo dõi kết quả (ChainTxResult). Mọi bảng chỉ ghi thêm, trừ AnchorState (một dòng: nonce kế tiếp, cờ dừng).

Trạng thái neo của một lần nộp suy ra từ bản ghi A/E của các file trong đó.
"""
import base64
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import anchor_payload
from app.core.log_record import GENESIS_HASH
from app.core.merkle import build_batch
from app.core.receipt import signing_public_key
from app.db.enums import AnchorStatus, ChainTxKind, ChainTxStatus
from app.db.models import AnchorBatch, AnchorLeaf, AnchorState, ChainTx, ChainTxResult, FileHash, LogRecord, Submission

logger = logging.getLogger(__name__)
EXPLORER_TX_URL = "https://sepolia.etherscan.io/tx/"
SIGNING_KEY_ID = 1
OK_STATUSES = (ChainTxStatus.CONFIRMED, ChainTxStatus.FINALIZED)


# ---------- Đọc trạng thái ----------

def _batch_results(db: Session, batch_ids) -> tuple[dict, set]:
    """batch_id -> (ChainTx ANCH đã lên khối, ChainTxResult CONFIRMED); tập batch_id có giao dịch FAILED."""
    confirmed, failed = {}, set()
    rows = db.execute(select(ChainTx, ChainTxResult).join(ChainTxResult, ChainTxResult.tx_id == ChainTx.id)
                      .where(ChainTx.batch_id.in_(batch_ids), ChainTx.kind == ChainTxKind.ANCH)).all()
    for tx, result in rows:
        if result.status == ChainTxStatus.CONFIRMED:
            confirmed[tx.batch_id] = (tx, result)
        elif result.status == ChainTxStatus.FAILED:
            failed.add(tx.batch_id)
    finalized = {tx.batch_id for tx, r in rows if r.status == ChainTxStatus.FINALIZED}
    return {b: (tx, r, b in finalized) for b, (tx, r) in confirmed.items()}, failed - confirmed.keys()


def anchor_state(db: Session, submission_id) -> tuple[AnchorStatus, ChainTxResult | None]:
    """ANCHORED khi bản ghi của mọi file nằm trong đợt có giao dịch đã lên khối (trả kết quả muộn nhất);
    ANCHOR_FAILED khi có đợt chứa bản ghi mà giao dịch lỗi. Job neo đang dừng thì bản ghi chưa vào đợt vẫn là chờ neo."""
    seqs = list(db.scalars(select(FileHash.record_seq).where(FileHash.submission_id == submission_id)))
    batch_of = dict(db.execute(select(AnchorLeaf.record_seq, AnchorLeaf.batch_id)
                               .where(AnchorLeaf.record_seq.in_(seqs))).all())
    confirmed, failed = _batch_results(db, set(batch_of.values()))
    if seqs and all(batch_of.get(s) in confirmed for s in seqs):
        return AnchorStatus.ANCHORED, max((confirmed[batch_of[s]][1] for s in seqs), key=lambda r: r.block_number)
    if any(batch_of.get(s) in failed for s in seqs):
        return AnchorStatus.ANCHOR_FAILED, None
    return AnchorStatus.PENDING_ANCHOR, None


def anchor_view(db: Session, submission: Submission) -> dict:
    """Phần thêm vào biên nhận hoàn chỉnh khi đã neo (F1-AC5): mỗi file một bản ghi 164 byte, đường dẫn hai tầng
    tới root đợt, payload đã gửi lên chuỗi."""
    files = list(db.scalars(select(FileHash).where(FileHash.submission_id == submission.id)
                            .order_by(FileHash.position)))
    seqs = [f.record_seq for f in files]
    records = {r.seq: r for r in db.scalars(select(LogRecord).where(LogRecord.seq.in_(seqs)))}
    leaves = {leaf.record_seq: leaf for leaf in db.scalars(select(AnchorLeaf).where(AnchorLeaf.record_seq.in_(seqs)))}
    batches = {b.id: b for b in db.scalars(select(AnchorBatch).where(
        AnchorBatch.id.in_({leaf.batch_id for leaf in leaves.values()})))}
    confirmed, _ = _batch_results(db, batches.keys())
    items = []
    for f in files:
        record, leaf = records[f.record_seq], leaves[f.record_seq]
        batch = batches[leaf.batch_id]
        tx, result, finalized = confirmed[batch.id]
        items.append({
            "fileCode": f.file_code, "seq": record.seq, "raw": record.raw.hex(), "recordHash": record.record_hash,
            "batchNo": batch.batch_no, "groupIndex": leaf.group_index, "leafIndex": leaf.leaf_index,
            "leafHash": leaf.leaf_hash, "groupPath": leaf.group_path, "batchPath": leaf.batch_path,
            "root": batch.root, "payload": batch.payload.hex(),
            "txHash": tx.tx_hash, "blockNumber": result.block_number,
            "blockTime": result.block_time.isoformat() if result.block_time else None,
            "finalized": finalized, "explorerUrl": EXPLORER_TX_URL + tx.tx_hash,
        })
    latest = max(items, key=lambda i: i["blockNumber"] or 0)  # các file thường cùng một đợt
    return {"mode": settings.anchor_mode.upper(), "txHash": latest["txHash"], "explorerUrl": latest["explorerUrl"],
            "blockTime": latest["blockTime"], "records": items}


# ---------- Worker ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _locked_state(db: Session) -> AnchorState:
    return db.get(AnchorState, 1, with_for_update=True)


def _halt(db: Session, reason: str) -> None:
    state = _locked_state(db)
    state.halted, state.halted_reason = True, reason[:1000]
    db.commit()
    logger.error("Dừng job neo: %s", reason)


def sync_nonce(db: Session, chain) -> None:
    """Chưa gửi giao dịch nào: lấy nonce của ví trên mạng. Đã gửi: nonce trên mạng vượt next_nonce nghĩa là ví bị
    dùng ngoài worker -> dừng, tránh trùng nonce."""
    state = _locked_state(db)
    chain_nonce = chain.pending_nonce()
    if db.scalar(select(ChainTx.id).limit(1)) is None:
        state.next_nonce = chain_nonce
    elif chain_nonce > state.next_nonce and not state.halted:
        state.halted = True
        state.halted_reason = f"Nonce của ví trên mạng ({chain_nonce}) vượt next_nonce ({state.next_nonce})."
        logger.error("Dừng job neo: %s", state.halted_reason)
    db.commit()


def _send(db: Session, chain, *, kind: ChainTxKind, nonce: int, payload: bytes, batch_id=None,
          replaces: ChainTx | None = None, bump: int = 0) -> ChainTx:
    """Ký, ghi ChainTx rồi mới phát: tiến trình chết sau commit thì lần sau vẫn theo dõi / thay thế được."""
    tx_hash, raw = chain.sign(nonce, payload, bump)
    tx = ChainTx(kind=kind, batch_id=batch_id, nonce=nonce, tx_hash=tx_hash, payload=payload,
                 replaces_tx_id=replaces.id if replaces else None, sent_at=_now())
    db.add(tx)
    db.commit()
    try:
        chain.broadcast(raw)
    except Exception as exc:  # lỗi mạng: giao dịch kẹt, sẽ được thay thế sau anchor_retry_seconds
        logger.warning("Phát giao dịch %s (nonce %s) lỗi: %s", tx_hash, nonce, exc)
    return tx


def ensure_key_registered(db: Session, chain) -> None:
    """KEYR là giao dịch đầu tiên của ví: đăng ký khóa ký biên nhận, áp dụng từ bản ghi from_seq."""
    if db.scalar(select(ChainTx.id).where(ChainTx.kind == ChainTxKind.KEYR).limit(1)):
        return
    state = _locked_state(db)
    if state.halted:
        db.rollback()
        return
    last = db.scalar(select(AnchorBatch).order_by(AnchorBatch.batch_no.desc()).limit(1))
    payload = anchor_payload.encode_keyr(SIGNING_KEY_ID, base64.b64decode(signing_public_key()),
                                         (last.to_seq if last else 0) + 1)
    nonce, state.next_nonce = state.next_nonce, state.next_nonce + 1
    _send(db, chain, kind=ChainTxKind.KEYR, nonce=nonce, payload=payload)


def cut_batch(db: Session, limit: int = 500) -> AnchorBatch | None:
    """Chốt đợt mới từ các bản ghi sau đợt trước (liền nhau), cấp nonce trong cùng thao tác database."""
    state = _locked_state(db)
    if state.halted:
        db.rollback()
        return None
    last = db.scalar(select(AnchorBatch).order_by(AnchorBatch.batch_no.desc()).limit(1))
    from_seq = (last.to_seq if last else 0) + 1
    records = list(db.scalars(select(LogRecord).where(LogRecord.seq >= from_seq).order_by(LogRecord.seq).limit(limit)))
    if not records:
        db.rollback()
        return None
    groups: dict = {}  # người ghi -> bản ghi; nhóm xếp theo bản ghi đầu tiên của nhóm
    for r in records:
        groups.setdefault(r.actor_id, []).append(r)
    root, proofs = build_batch([[r.record_hash for r in g] for g in groups.values()])
    batch_no, prev_root = (last.batch_no + 1, last.root) if last else (1, GENESIS_HASH)
    batch = AnchorBatch(batch_no=batch_no, from_seq=from_seq, to_seq=records[-1].seq, prev_root=prev_root, root=root,
                        payload=anchor_payload.encode_anch(batch_no, from_seq, records[-1].seq, prev_root, root),
                        nonce=state.next_nonce)
    state.next_nonce += 1
    db.add(batch)
    db.flush()
    for g, (group, group_proofs) in enumerate(zip(groups.values(), proofs)):
        for i, (record, proof) in enumerate(zip(group, group_proofs)):
            db.add(AnchorLeaf(batch_id=batch.id, record_seq=record.seq, group_index=g, leaf_index=i,
                              leaf_hash=proof["leafHash"], group_path=proof["groupPath"],
                              batch_path=proof["batchPath"]))
    db.commit()
    return batch


def send_unsent_batches(db: Session, chain) -> None:
    """Đợt đã chốt nhưng chưa có giao dịch (mới chốt, hoặc tiến trình chết trước khi ký)."""
    sent = select(ChainTx.batch_id).where(ChainTx.batch_id.is_not(None))
    for batch in db.scalars(select(AnchorBatch).where(AnchorBatch.id.not_in(sent)).order_by(AnchorBatch.batch_no)):
        _send(db, chain, kind=ChainTxKind.ANCH, nonce=batch.nonce, payload=batch.payload, batch_id=batch.id)


def poll_transactions(db: Session, chain) -> None:
    """Ghi CONFIRMED / FAILED khi giao dịch lên khối, FINALIZED khi khối đã chốt; giao dịch kẹt quá
    anchor_retry_seconds thì gửi lại cùng payload, cùng nonce, phí cao hơn."""
    txs = list(db.scalars(select(ChainTx).order_by(ChainTx.sent_at)))
    statuses: dict = {}
    for r in db.scalars(select(ChainTxResult)):
        statuses.setdefault(r.tx_id, {})[r.status] = r
    done_nonces = {tx.nonce for tx in txs if statuses.get(tx.id)}
    replaced = {tx.replaces_tx_id for tx in txs if tx.replaces_tx_id}
    finalized_block = None

    for tx in txs:
        seen = statuses.get(tx.id, {})
        if ChainTxStatus.CONFIRMED in seen and ChainTxStatus.FINALIZED not in seen:
            confirmed = seen[ChainTxStatus.CONFIRMED]
            finalized_block = finalized_block if finalized_block is not None else chain.finalized_block()
            if confirmed.block_number <= finalized_block:
                db.add(ChainTxResult(tx_id=tx.id, status=ChainTxStatus.FINALIZED, block_number=confirmed.block_number,
                                     block_time=confirmed.block_time, observed_at=_now()))
                db.commit()
            continue
        if seen or tx.nonce in done_nonces:  # đã có kết quả, hoặc giao dịch khác cùng nonce đã lên khối
            continue
        receipt = chain.receipt(tx.tx_hash)
        if receipt:
            status = ChainTxStatus.CONFIRMED if receipt["success"] else ChainTxStatus.FAILED
            db.add(ChainTxResult(tx_id=tx.id, status=status, block_number=receipt["blockNumber"],
                                 block_time=datetime.fromtimestamp(receipt["blockTime"], tz=timezone.utc),
                                 observed_at=_now()))
            db.commit()
            done_nonces.add(tx.nonce)
            logger.info("Giao dịch %s %s (nonce %s): %s", tx.kind.value, tx.tx_hash, tx.nonce, status.value)
            if status == ChainTxStatus.FAILED:
                _halt(db, f"Giao dịch {tx.kind.value} {tx.tx_hash} (nonce {tx.nonce}) thất bại trên chuỗi.")
        elif tx.id not in replaced and _now() - tx.sent_at > timedelta(seconds=settings.anchor_retry_seconds):
            depth, cur = 1, tx
            while cur.replaces_tx_id:
                depth, cur = depth + 1, db.get(ChainTx, cur.replaces_tx_id)
            new = _send(db, chain, kind=tx.kind, nonce=tx.nonce, payload=tx.payload, batch_id=tx.batch_id,
                        replaces=tx, bump=depth)
            logger.warning("Giao dịch %s kẹt, gửi lại %s (nonce %s)", tx.tx_hash, new.tx_hash, tx.nonce)
