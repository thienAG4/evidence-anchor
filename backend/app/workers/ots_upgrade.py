r"""Chạy nâng cấp OpenTimestamps một lần (worker neo tự chạy mỗi OTS_UPGRADE_SECONDS).

Chạy (từ thư mục backend/): ..\venv\Scripts\python.exe -m app.workers.ots_upgrade
"""
import logging

from app.db.session import SessionLocal
from app.services import ots_service

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    with SessionLocal() as db:
        print(ots_service.upgrade_pending(db))
