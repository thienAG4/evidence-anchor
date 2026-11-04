"""Ghi AccessLog mọi request, kể cả bị từ chối (DENY) — F8-AC4. Bảng chỉ ghi thêm."""
import ipaddress
import logging
import uuid

import jwt
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.security import decode_access_token
from app.db.enums import AccessResult
from app.db.models import AccessLog, Dossier
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
SKIP_PATHS = ("/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico")
DENY_STATUSES = {401, 403}  # chưa đăng nhập / không có quyền


def _token_claims(scope: Scope) -> dict:
    for name, value in scope.get("headers", []):
        if name == b"authorization" and value.lower().startswith(b"bearer "):
            try:
                return decode_access_token(value[7:].decode())
            except (jwt.PyJWTError, UnicodeDecodeError):
                return {}
    return {}


def _to_uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


def _client_ip(scope: Scope) -> str | None:
    """Chỉ ghi khi là địa chỉ IP thật (cột INET); 'testclient', unix socket... thì để trống, không mất dòng log."""
    client = scope.get("client")
    try:
        return str(ipaddress.ip_address(client[0])) if client else None
    except ValueError:
        return None


def write_log(scope: Scope, status: int) -> None:
    route = scope.get("route")
    if not isinstance(route, APIRoute) and status not in DENY_STATUSES:
        return  # file giao diện (html, css, ảnh) hay đường dẫn lạ: không ghi
    claims = _token_claims(scope)
    params = scope.get("path_params") or {}
    with SessionLocal() as db:
        case_id = _to_uuid(params.get("case_id"))
        if case_id is None and params.get("dossier_id"):
            dossier = db.get(Dossier, _to_uuid(params["dossier_id"])) if _to_uuid(params["dossier_id"]) else None
            case_id = dossier.case_id if dossier else None
        db.add(AccessLog(
            user_id=_to_uuid(claims.get("sub")), role=claims.get("role"),
            action=f"{scope['method']} {getattr(route, 'path', scope['path'])}"[:60],
            resource=scope["path"][:100], case_id=case_id,
            result=AccessResult.DENY if status in DENY_STATUSES else AccessResult.ALLOW,
            ip=_client_ip(scope),
        ))
        db.commit()


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope["path"].startswith(SKIP_PATHS):
            return await self.app(scope, receive, send)
        status = {"code": 500}

        async def send_with_status(message: Message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            try:
                await run_in_threadpool(write_log, scope, status["code"])
            except Exception:  # ghi log lỗi không được làm hỏng response đã gửi
                logger.exception("Không ghi được AccessLog")
