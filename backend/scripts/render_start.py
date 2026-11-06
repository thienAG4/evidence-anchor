"""Khởi động trên Render (render.yaml, startCommand): DB -> migration -> seed -> worker neo -> API.

Render free không có background worker, nên worker neo chạy là tiến trình con trong cùng web service.
Vẫn chỉ 1 tiến trình gửi giao dịch, nên nonce cấp từ AnchorState không trùng.

Biến môi trường (đặt trên Render):
  DB_OWNER_URL      chuỗi kết nối Postgres của Render (chủ sở hữu bảng, chạy migration)
  APP_DB_PASSWORD   mật khẩu cho role evidence_app (ít quyền, F6); không tạo được role thì dùng chủ sở hữu
  PRIVATE_KEY, ANCHOR_WALLET_ADDRESS, RECEIPT_SIGNING_KEY, JWT_SECRET ... như .env.example
"""
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_ROLE = "evidence_app"


def sqlalchemy_url(url: str) -> str:
    """Render cho postgres:// hoặc postgresql://; SQLAlchemy cần driver psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def libpq_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def with_user(url: str, user: str, password: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname + (f":{parts.port}" if parts.port else "")
    return urlunsplit(parts._replace(netloc=f"{quote(user, safe='')}:{quote(password, safe='')}@{host}"))


def ensure_app_role(owner_url: str, password: str) -> bool:
    """Tạo (hoặc đặt lại mật khẩu) role evidence_app trước migration để migration cấp quyền chỉ ghi thêm cho nó."""
    import psycopg
    from psycopg import sql

    dbname = urlsplit(owner_url).path.lstrip("/")
    try:
        with psycopg.connect(libpq_url(owner_url), autocommit=True) as conn:
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(APP_ROLE),
                                                                            sql.Literal(password)))
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname),
                                                                             sql.Identifier(APP_ROLE)))
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(APP_ROLE)))
        return True
    except psycopg.Error as exc:
        print(f"[deploy] Không tạo được role {APP_ROLE} ({exc}). Ứng dụng chạy bằng tài khoản chủ sở hữu bảng.",
              file=sys.stderr)
        return False


def main() -> None:
    owner = os.environ.get("DB_OWNER_URL")
    if not owner:
        sys.exit("[deploy] Thiếu DB_OWNER_URL (chuỗi kết nối Postgres).")
    owner = sqlalchemy_url(owner)
    app_password = os.environ.get("APP_DB_PASSWORD")

    env = os.environ.copy()
    env["MIGRATION_DATABASE_URL"] = owner
    use_app_role = bool(app_password) and ensure_app_role(owner, app_password)
    env["DATABASE_URL"] = with_user(owner, APP_ROLE, app_password) if use_app_role else owner
    print(f"[deploy] Ứng dụng kết nối DB bằng {'evidence_app' if use_app_role else 'chủ sở hữu bảng'}.")

    def run(*args: str) -> None:
        subprocess.run([sys.executable, *args], cwd=BACKEND_DIR, env=env, check=True)

    run("-m", "alembic", "upgrade", "head")
    run("scripts/seed.py")

    if env.get("PRIVATE_KEY"):
        subprocess.Popen([sys.executable, "-m", "app.workers.anchor_worker"], cwd=BACKEND_DIR, env=env)
        print("[deploy] Đã chạy worker neo.")
    else:
        print("[deploy] Chưa có PRIVATE_KEY: không chạy worker neo, biên nhận ở trạng thái Chờ neo.")

    os.chdir(BACKEND_DIR)
    os.execve(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
                               "--port", env.get("PORT", "8000"), "--proxy-headers",
                               "--forwarded-allow-ips=*"], env)


if __name__ == "__main__":
    main()
