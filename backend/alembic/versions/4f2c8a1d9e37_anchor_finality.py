"""anchor_finality: ghi thêm khi block chứa giao dịch neo đã chốt (finalized)

Revision ID: 4f2c8a1d9e37
Revises: 9b1ed68a757b
Create Date: 2026-11-04 22:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '4f2c8a1d9e37'
down_revision: Union[str, None] = '9b1ed68a757b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "evidence_app"


def upgrade() -> None:
    op.create_table(
        'anchor_finality',
        sa.Column('anchor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tx_block_number', sa.BigInteger(), nullable=False),
        sa.Column('finalized_block_number', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['anchor_id'], ['anchor.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('anchor_id'),
    )
    # F6: bảng chỉ ghi thêm — tài khoản ứng dụng chỉ SELECT, INSERT
    op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN "
               f"EXECUTE 'GRANT SELECT, INSERT ON anchor_finality TO {APP_ROLE}'; END IF; END $$")


def downgrade() -> None:
    op.drop_table('anchor_finality')
