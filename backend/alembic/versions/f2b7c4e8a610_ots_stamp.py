"""ots_stamp: OpenTimestamps cho bản ghi A (Final_ERD, thêm stamped_at để báo động sau 48 giờ)

Revision ID: f2b7c4e8a610
Revises: d5f8a2c6b913
Create Date: 2026-11-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f2b7c4e8a610'
down_revision: Union[str, None] = 'd5f8a2c6b913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
APP_ROLE = "evidence_app"


def _grant(statements: list[str]) -> None:
    body = " ".join(f"EXECUTE '{s} TO {APP_ROLE}';" for s in statements)
    op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN {body} END IF; END $$")


def upgrade() -> None:
    op.create_table(
        'ots_stamp',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('record_seq', sa.BigInteger(), sa.ForeignKey('log_record.seq'), nullable=False, unique=True),
        sa.Column('file_hash', sa.CHAR(64), nullable=False),
        sa.Column('ots_pending', sa.LargeBinary(), nullable=False),
        sa.Column('ots_complete', sa.LargeBinary(), nullable=True),
        sa.Column('bitcoin_block', sa.BigInteger(), nullable=True),
        sa.Column('stamped_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('upgraded_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Bảng được sửa (điền bản hoàn chỉnh), nhưng không được xóa
    _grant(["GRANT SELECT, INSERT, UPDATE ON ots_stamp"])


def downgrade() -> None:
    op.drop_table('ots_stamp')
