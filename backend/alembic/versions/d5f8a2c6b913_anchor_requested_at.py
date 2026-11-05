"""anchor_requested_at: nút "Neo ngay" (worker chốt đợt không đợi mốc ngày)

Revision ID: d5f8a2c6b913
Revises: b3e1f6a9c207
Create Date: 2026-11-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd5f8a2c6b913'
down_revision: Union[str, None] = 'b3e1f6a9c207'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # anchor_state đã có quyền UPDATE cho evidence_app (e7a3b9c2d4f1), không cần cấp thêm
    op.add_column('anchor_state', sa.Column('anchor_requested_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('anchor_state', 'anchor_requested_at')
