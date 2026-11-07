"""anchor_batch: neo theo đợt (AnchorBatch, AnchorLeaf hai tầng, ChainTx, ChainTxResult, AnchorState); seq LogRecord
không dùng sequence

Revision ID: e7a3b9c2d4f1
Revises: c4d2a7e91f05
Create Date: 2026-11-05 15:00:00.000000

Bảng Anchor / AnchorLeaf cũ (mỗi lần thử neo một dòng, cây một tầng) không chuyển sang đợt được -> bỏ, worker neo lại
mọi bản ghi từ seq 1. anchor_state.next_nonce = 0: worker lấy nonce của ví trên mạng khi chưa có ChainTx nào.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e7a3b9c2d4f1'
down_revision: Union[str, None] = 'c4d2a7e91f05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "evidence_app"


def _grant(statements: list[str]) -> None:
    body = " ".join(f"EXECUTE '{s} TO {APP_ROLE}';" for s in statements)
    op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN {body} END IF; END $$")


def upgrade() -> None:
    # LogRecord: seq = seq cuối + 1 (log_service), chuỗi không rẽ nhánh
    op.execute("DROP SEQUENCE IF EXISTS log_record_seq")
    op.create_unique_constraint('log_record_prev_record_hash_key', 'log_record', ['prev_record_hash'])

    # anchor_finality (4f2c8a1d9e37) trỏ vào anchor: bỏ trước; FINALIZED giờ ghi ở chain_tx_result.
    # IF EXISTS: DB đã chạy migration này trước khi nối sau 4f2c8a1d9e37 thì không có bảng đó.
    op.execute("DROP TABLE IF EXISTS anchor_finality")
    op.drop_table('anchor_leaf')
    op.drop_table('anchor')
    op.execute("DROP TYPE IF EXISTS anchor_mode")
    op.execute("DROP TYPE IF EXISTS anchor_result")

    op.create_table('anchor_batch',
    sa.Column('batch_no', sa.BigInteger(), nullable=False),
    sa.Column('from_seq', sa.BigInteger(), nullable=False),
    sa.Column('to_seq', sa.BigInteger(), nullable=False),
    sa.Column('prev_root', sa.CHAR(length=64), nullable=False),
    sa.Column('root', sa.CHAR(length=64), nullable=False),
    sa.Column('payload', sa.LargeBinary(), nullable=False),
    sa.Column('nonce', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.CheckConstraint('from_seq <= to_seq', name='seq_range'),
    sa.ForeignKeyConstraint(['from_seq'], ['log_record.seq'], ),
    sa.ForeignKeyConstraint(['to_seq'], ['log_record.seq'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('batch_no'),
    sa.UniqueConstraint('nonce')
    )
    op.create_table('anchor_leaf',
    sa.Column('batch_id', sa.UUID(), nullable=False),
    sa.Column('record_seq', sa.BigInteger(), nullable=False),
    sa.Column('group_index', sa.Integer(), nullable=False),
    sa.Column('leaf_index', sa.Integer(), nullable=False),
    sa.Column('leaf_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('group_path', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('batch_path', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['anchor_batch.id'], ),
    sa.ForeignKeyConstraint(['record_seq'], ['log_record.seq'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('batch_id', 'group_index', 'leaf_index'),
    sa.UniqueConstraint('record_seq')
    )
    op.create_table('chain_tx',
    sa.Column('kind', sa.Enum('ANCH', 'KEYR', 'NOOP', name='chain_tx_kind'), nullable=False),
    sa.Column('batch_id', sa.UUID(), nullable=True),
    sa.Column('nonce', sa.BigInteger(), nullable=False),
    sa.Column('tx_hash', sa.CHAR(length=66), nullable=False),
    sa.Column('payload', sa.LargeBinary(), nullable=False),
    sa.Column('replaces_tx_id', sa.UUID(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['anchor_batch.id'], ),
    sa.ForeignKeyConstraint(['replaces_tx_id'], ['chain_tx.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tx_hash')
    )
    op.create_index(op.f('ix_chain_tx_batch_id'), 'chain_tx', ['batch_id'], unique=False)
    op.create_table('chain_tx_result',
    sa.Column('tx_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('CONFIRMED', 'FINALIZED', 'FAILED', name='chain_tx_status'), nullable=False),
    sa.Column('block_number', sa.BigInteger(), nullable=True),
    sa.Column('block_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['tx_id'], ['chain_tx.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tx_id', 'status')
    )
    op.create_table('anchor_state',
    sa.Column('id', sa.SmallInteger(), autoincrement=False, nullable=False),
    sa.Column('next_nonce', sa.BigInteger(), nullable=False),
    sa.Column('halted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('halted_reason', sa.Text(), nullable=True),
    sa.CheckConstraint('id = 1', name='single_row'),
    sa.PrimaryKeyConstraint('id')
    )
    op.execute("INSERT INTO anchor_state (id, next_nonce, halted) VALUES (1, 0, false)")

    # F6: bảng neo chỉ ghi thêm; anchor_state chỉ được sửa (không thêm, không xóa)
    _grant(["GRANT SELECT, INSERT ON anchor_batch, anchor_leaf, chain_tx, chain_tx_result",
            "GRANT SELECT, UPDATE ON anchor_state"])


def downgrade() -> None:
    op.drop_table('anchor_state')
    op.drop_table('chain_tx_result')
    op.drop_index(op.f('ix_chain_tx_batch_id'), table_name='chain_tx')
    op.drop_table('chain_tx')
    op.drop_table('anchor_leaf')
    op.drop_table('anchor_batch')
    op.execute("DROP TYPE IF EXISTS chain_tx_status")
    op.execute("DROP TYPE IF EXISTS chain_tx_kind")

    op.create_table('anchor',
    sa.Column('mode', sa.Enum('PER_SUBMISSION', 'DAILY', name='anchor_mode'), nullable=False),
    sa.Column('period_date', sa.Date(), nullable=True),
    sa.Column('root_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('leaf_count', sa.Integer(), nullable=False),
    sa.Column('result', sa.Enum('CONFIRMED', 'FAILED', name='anchor_result'), nullable=False),
    sa.Column('tx_hash', sa.CHAR(length=66), nullable=True),
    sa.Column('block_number', sa.BigInteger(), nullable=True),
    sa.Column('block_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('anchor_leaf',
    sa.Column('anchor_id', sa.UUID(), nullable=False),
    sa.Column('record_seq', sa.BigInteger(), nullable=False),
    sa.Column('leaf_index', sa.Integer(), nullable=False),
    sa.Column('merkle_proof', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['anchor_id'], ['anchor.id'], ),
    sa.ForeignKeyConstraint(['record_seq'], ['log_record.seq'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('anchor_id', 'record_seq')
    )
    op.create_index(op.f('ix_anchor_leaf_record_seq'), 'anchor_leaf', ['record_seq'], unique=False)
    op.create_table('anchor_finality',
    sa.Column('anchor_id', sa.UUID(), nullable=False),
    sa.Column('tx_block_number', sa.BigInteger(), nullable=False),
    sa.Column('finalized_block_number', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['anchor_id'], ['anchor.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('anchor_id')
    )
    _grant(["GRANT SELECT, INSERT ON anchor, anchor_leaf, anchor_finality"])

    op.drop_constraint('log_record_prev_record_hash_key', 'log_record', type_='unique')
    op.execute("CREATE SEQUENCE log_record_seq")
    op.execute("SELECT setval('log_record_seq', GREATEST((SELECT COALESCE(MAX(seq), 0) FROM log_record), 1))")
    _grant(["GRANT USAGE, SELECT ON SEQUENCE log_record_seq"])
