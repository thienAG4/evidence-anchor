"""Tiến trình riêng: mỗi vòng theo dõi giao dịch đã gửi, chốt một đợt từ các LogRecord chưa neo rồi gửi giao dịch
ANCH (per_submission: đợt chốt ngay vòng sau khi có bản ghi; daily: mỗi ngày một đợt ở mốc ANCHOR_DAILY_CUTOFF, nút Neo ngay chốt sớm). Giao dịch đầu tiên của ví là KEYR.

Chạy (từ thư mục backend/): ..\\venv\\Scripts\\python.exe -m app.workers.anchor_worker

Tách khỏi server API vì: (1) chỉ 1 nơi gửi giao dịch -> nonce cấp từ AnchorState không trùng;
(2) nạp web3 trong tiến trình uvicorn làm --reload trên Windows treo.

chain cần: address, pending_nonce(), sign(nonce, data, bump) -> (tx_hash, raw), broadcast(raw),
receipt(tx_hash) -> {success, blockNumber, blockTime} | None, finalized_block().
"""
import logging
import threading
import time

from app.config import settings
from app.db.models import AnchorState
from app.db.session import SessionLocal
from app.services import anchor_service, ots_service

logger = logging.getLogger("anchor_worker")


def run_once(chain) -> int:
    """Một vòng neo. Trả về số bản ghi trong đợt vừa chốt (0 nếu không chốt đợt nào)."""
    with SessionLocal() as db:
        anchor_service.sync_nonce(db, chain)
        anchor_service.poll_transactions(db, chain)
        if db.get(AnchorState, 1).halted:
            logger.warning("Job neo đang dừng: %s", db.get(AnchorState, 1).halted_reason)
            return 0
        anchor_service.ensure_key_registered(db, chain)
        if settings.anchor_mode == "daily":
            forced = anchor_service.take_anchor_request(db)
            if forced:
                logger.info("Có yêu cầu Neo ngay: chốt các bản ghi đang chờ, không đợi mốc %s",
                            settings.anchor_daily_cutoff)
            batches = anchor_service.cut_due_batches(db, force=forced)
        else:  # per_submission (demo): mọi bản ghi đang chờ vào đợt ngay vòng này; Neo ngay không cần làm gì thêm
            anchor_service.take_anchor_request(db)
            batches = [b for b in [anchor_service.cut_batch(db)] if b]
        anchor_service.send_unsent_batches(db, chain)
        anchor_service.poll_transactions(db, chain)  # mạng nhanh (hoặc chuỗi giả khi kiểm thử): có kết quả ngay
        for batch in batches:
            logger.info("Đợt %s: bản ghi %s..%s, root %s", batch.batch_no, batch.from_seq, batch.to_seq, batch.root)
        return sum(b.to_seq - b.from_seq + 1 for b in batches)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if settings.anchor_mode not in ("per_submission", "daily"):
        raise SystemExit(f"ANCHOR_MODE={settings.anchor_mode} không hỗ trợ (per_submission | daily).")
    if not settings.private_key:
        raise SystemExit("Chưa có PRIVATE_KEY trong .env: không neo được, biên nhận sẽ ở trạng thái PENDING_ANCHOR.")
    from app.core import chain  # nạp web3, đọc SEPOLIA_RPC_URL, PRIVATE_KEY

    configured = (settings.anchor_wallet_address or "").lower()
    if configured and configured != chain.account.address.lower():
        raise SystemExit(f"ANCHOR_WALLET_ADDRESS ({settings.anchor_wallet_address}) không phải ví của PRIVATE_KEY "
                         f"({chain.account.address}): /verify sẽ báo sai ví gửi.")
    if not configured:
        logger.warning("Chưa có ANCHOR_WALLET_ADDRESS=%s trong .env: /verify sẽ không kiểm được ví gửi.",
                       chain.account.address)

    logger.info("Worker neo chạy, ví %s, mỗi %ss", chain.account.address, settings.anchor_interval_seconds)
    stop = threading.Event()
    next_ots = 0.0
    try:
        while not stop.is_set():
            try:
                run_once(chain)
            except Exception:
                logger.exception("Vòng neo lỗi")
            if time.monotonic() >= next_ots:  # OpenTimestamps: nâng cấp bản chờ mỗi OTS_UPGRADE_SECONDS (6.9)
                next_ots = time.monotonic() + settings.ots_upgrade_seconds
                try:
                    with SessionLocal() as db:
                        result = ots_service.upgrade_pending(db)
                    if result["upgraded"] or result["pending"]:
                        logger.info("OpenTimestamps: %s", result)
                except Exception:
                    logger.exception("Nâng cấp OpenTimestamps lỗi")
            stop.wait(settings.anchor_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Dừng worker neo.")


if __name__ == "__main__":
    main()
