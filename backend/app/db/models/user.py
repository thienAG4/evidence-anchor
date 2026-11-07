from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk
from app.db.enums import UserRole, UserStatus


class User(UUIDPk, Base):
    """Tài khoản có sẵn (seed / admin tạo), đăng nhập bằng tên đăng nhập + mật khẩu."""
    __tablename__ = "user_account"  # "user" là từ khóa của PostgreSQL

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    court_name: Mapped[str | None] = mapped_column(String(200))  # Tòa của CLERK, JUDGE
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.ACTIVE)
