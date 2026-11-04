"""Tiến trình riêng: per_submission neo từng lần nộp chưa neo; thử lại khi FAILED. (daily: chưa làm.)

Chạy (từ thư mục backend/): ..\\venv\\Scripts\\python.exe -m app.workers.anchor_worker

Tách khỏi server API vì: (1) chỉ 1 nơi gửi giao dịch -> không trùng nonce dù chạy nhiều worker API;
(2) nạp web3 trong tiến trình uvicorn làm --reload trên Windows treo.
"""
import logging
import threading

from app.config import settings
from app.db.session import SessionLocal
from app.services.anchor_service import anchor_submission, submissions_to_anchor

logger = logging.getLogger("anchor_worker")


def run_once(chain) -> int:
    """Neo các lần nộp đang chờ. Trả về số lần đã thử."""
    count = 0
    with SessionLocal() as db:
        for submission in submissions_to_anchor(db):
            anchor = anchor_submission(db, chain, submission)
            logger.info("Neo %s: %s %s", submission.receipt_code, anchor.result.value, anchor.tx_hash or anchor.error)
            count += 1
    return count


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if settings.anchor_mode != "per_submission":
        raise SystemExit(f"ANCHOR_MODE={settings.anchor_mode} chưa hỗ trợ.")
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
    try:
        while not stop.is_set():
            try:
                run_once(chain)
            except Exception:
                logger.exception("Vòng neo lỗi")
            stop.wait(settings.anchor_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Dừng worker neo.")


if __name__ == "__main__":
    main()
