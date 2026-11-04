from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Đường dẫn tuyệt đối: chạy từ gốc repo hay từ backend/ đều đọc được. File sau ghi đè file trước.
    model_config = SettingsConfigDict(env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"), extra="ignore")

    database_url: str  # tài khoản ứng dụng (evidence_app)
    migration_database_url: str | None = None  # chủ sở hữu bảng, cho alembic; trống thì dùng database_url
    sepolia_rpc_url: str = "https://ethereum-sepolia-rpc.publicnode.com"
    private_key: str | None = None  # ví TEST gửi giao dịch neo; trống thì worker không neo
    anchor_wallet_address: str | None = None  # địa chỉ ví đó (công khai), để /verify kiểm ai gửi giao dịch
    receipt_signing_key: str  # khóa secp256k1 32 byte hex, ký biên nhận tạm (EIP-191); khác khóa ví neo
    receipt_key_no: int = 1  # số khóa ký đang dùng (KEYR/KREV công bố, thu hồi theo số này)
    # Địa chỉ khóa ký đã công bố; /verify so chữ ký với địa chỉ này. Trống thì lấy từ RECEIPT_SIGNING_KEY.
    receipt_signer_address: str | None = None
    jwt_secret: str
    jwt_expire_minutes: int = 480
    anchor_mode: str = "per_submission"  # per_submission (demo) | daily
    anchor_interval_seconds: int = 15
    anchor_retry_seconds: int = 60  # neo lỗi thì chờ bấy nhiêu giây mới thử lại
    # Thư ký chỉ đối chiếu biên nhận đã neo ("Đã khóa"). Máy dev chưa chạy worker neo thì đặt false để test.
    require_anchor_before_verify: bool = True
    # Giao diện chạy riêng (Live Server :5500, mở file trực tiếp = origin "null") được gọi API
    cors_origins: list[str] = ["http://localhost:5500", "http://127.0.0.1:5500", "null"]
    max_file_mb: int = 500
    max_files_per_submission: int = 50


settings = Settings()
