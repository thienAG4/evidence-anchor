"""Tạo FastAPI app, gắn router, middleware, exception handler, phục vụ thư mục frontend/.

Chạy (từ gốc repo): venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend
Giao diện: http://localhost:8000 · Tài liệu API: http://localhost:8000/docs
Worker neo chạy tiến trình riêng: xem app/workers/anchor_worker.py.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import BACKEND_DIR, settings
from app.errors.handlers import register_error_handlers
from app.middleware.access_log import AccessLogMiddleware
from app.routers import admin, auth, cases, clerk, dossiers, lots, submissions, verify

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"

app = FastAPI(title="EvidenceChain API", version="0.4.0")
register_error_handlers(app)
app.add_middleware(AccessLogMiddleware)
# Gọi API bằng header Authorization (không dùng cookie) nên mở CORS cho giao diện chạy riêng không gây CSRF
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                   allow_headers=["Authorization", "Content-Type"])
for module in (auth, submissions, clerk, cases, lots, dossiers, verify, admin):
    app.include_router(module.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Gắn sau cùng: đường dẫn nào không phải API thì lấy file trong frontend/ (/ -> index.html)
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
