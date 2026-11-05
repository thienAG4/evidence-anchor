"""record_layout_v1: mã hóa lại LogRecord theo bố cục EVC-REC-v1 (app.core.record, tài liệu kỹ thuật 5.4.1)

Revision ID: b3e1f6a9c207
Revises: e7a3b9c2d4f1
Create Date: 2026-11-06 10:00:00.000000

c4d2a7e91f05 ghi bản ghi theo bố cục tạm (UUID dạng chữ). Migration này tính lại raw, record_hash, prev_record_hash
của mọi bản ghi theo seq tăng dần, từ các cột đã lưu. Hash bản ghi đổi nên đợt neo cũ (nếu có) không còn khớp:
xóa đợt neo, worker neo lại từ seq 1 (anchor_state.next_nonce = 0: worker lấy lại nonce của ví trên mạng).
"""
import hashlib
import struct
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b3e1f6a9c207'
down_revision: Union[str, None] = 'e7a3b9c2d4f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LAYOUT = struct.Struct(">10sQB32s32s32sQBQ32s")  # giữ nguyên app.core.record lúc viết migration này


def _ref32(value) -> bytes:
    return bytes(32) if value is None else uuid.UUID(str(value)).bytes + bytes(16)


def upgrade() -> None:
    bind = op.get_bind()
    sent = bind.execute(sa.text("SELECT count(*) FROM chain_tx")).scalar()
    if sent:
        print(f"Cảnh báo: xóa {sent} ChainTx cũ (neo theo bố cục bản ghi cũ), worker neo lại từ seq 1.")
    for table in ("chain_tx_result", "chain_tx", "anchor_leaf", "anchor_batch"):
        op.execute(f"DELETE FROM {table}")
    op.execute("UPDATE anchor_state SET next_nonce = 0, halted = false, halted_reason = NULL")

    prev = bytes(32)
    rows = bind.execute(sa.text(
        "SELECT seq, event_type, file_hash, case_id, actor_id, ts, result, ref_seq FROM log_record ORDER BY seq"))
    for r in rows.mappings().all():
        raw = _LAYOUT.pack(b"EVC-REC-v1", r["seq"], r["event_type"], bytes.fromhex(r["file_hash"]),
                           _ref32(r["case_id"]), _ref32(r["actor_id"]), r["ts"], r["result"], r["ref_seq"] or 0, prev)
        record_hash = hashlib.sha256(raw).digest()
        bind.execute(sa.text("UPDATE log_record SET raw = :raw, record_hash = :h, prev_record_hash = :p WHERE seq = :seq"),
                     {"raw": raw, "h": record_hash.hex(), "p": prev.hex(), "seq": r["seq"]})
        prev = record_hash


def downgrade() -> None:
    raise NotImplementedError("Không quay lại bố cục bản ghi tạm; dựng lại DB nếu cần.")
