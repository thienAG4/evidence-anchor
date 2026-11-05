"""log_record: bản ghi sự kiện 164 byte nối chuỗi, record_seq, AnchorLeaf trỏ LogRecord

Revision ID: c4d2a7e91f05
Revises: 9b1ed68a757b
Create Date: 2026-11-05 10:00:00.000000

Dữ liệu cũ: mỗi dòng FileHash / AppraisalStep / Dossier / IntegrityCheck được ghi bù một LogRecord theo thứ tự thời
gian. IntegrityCheck cũ không lưu hash của file được đối chiếu, nên bản ghi bù dùng hash của bản đã ghi (file, lô,
danh mục). AnchorLeaf cũ neo bundle_hash, không chuyển sang lá bản ghi được -> xóa Anchor/AnchorLeaf cũ, worker neo lại.
"""
import hashlib
import struct
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c4d2a7e91f05'
down_revision: Union[str, None] = '9b1ed68a757b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "evidence_app"
LINKED_TABLES = ("file_hash", "appraisal_step", "dossier", "integrity_check")
NIL_UUID = "00000000-0000-0000-0000-000000000000"
RESULT_CODES = {None: 0, "UNCHANGED": 1, "CHANGED": 2, "NO_BASELINE": 3}


def _encode(seq, event_type, file_hash, case_id, actor_id, ts, result, ref_seq, prev):
    """Giữ nguyên bố cục của app.core.log_record lúc viết migration này."""
    raw = (struct.pack(">QH", seq, event_type) + bytes.fromhex(file_hash)
           + str(case_id or NIL_UUID).encode("ascii") + str(actor_id).encode("ascii")
           + struct.pack(">QHQ", ts, result, ref_seq or 0) + bytes.fromhex(prev))
    assert len(raw) == 164
    return raw


def upgrade() -> None:
    op.execute("CREATE SEQUENCE log_record_seq START 1")
    op.create_table('log_record',
    sa.Column('seq', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('event_type', sa.SmallInteger(), nullable=False),
    sa.Column('file_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('actor_id', sa.UUID(), nullable=False),
    sa.Column('ts', sa.BigInteger(), nullable=False),
    sa.Column('result', sa.SmallInteger(), nullable=False),
    sa.Column('ref_seq', sa.BigInteger(), nullable=True),
    sa.Column('prev_record_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('record_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('raw', sa.LargeBinary(), nullable=False),
    sa.CheckConstraint('event_type BETWEEN 1 AND 4', name='event_type_range'),
    sa.CheckConstraint('result BETWEEN 0 AND 3', name='result_range'),
    sa.CheckConstraint('octet_length(raw) = 164', name='raw_164_bytes'),
    sa.ForeignKeyConstraint(['actor_id'], ['user_account.id'], ),
    sa.ForeignKeyConstraint(['case_id'], ['court_case.id'], ),
    sa.ForeignKeyConstraint(['ref_seq'], ['log_record.seq'], ),
    sa.PrimaryKeyConstraint('seq'),
    sa.UniqueConstraint('record_hash')
    )
    op.create_index(op.f('ix_log_record_case_id'), 'log_record', ['case_id'], unique=False)
    op.create_index(op.f('ix_log_record_file_hash'), 'log_record', ['file_hash'], unique=False)

    for table in LINKED_TABLES:
        op.add_column(table, sa.Column('record_seq', sa.BigInteger(), nullable=True))
    _backfill(op.get_bind())
    for table in LINKED_TABLES:
        op.alter_column(table, 'record_seq', nullable=False)
        op.create_foreign_key(f'{table}_record_seq_fkey', table, 'log_record', ['record_seq'], ['seq'])
        op.create_unique_constraint(f'{table}_record_seq_key', table, ['record_seq'])

    op.execute("DELETE FROM anchor_leaf")
    op.execute("DELETE FROM anchor")
    op.drop_column('anchor_leaf', 'submission_id')  # kéo theo unique (anchor_id, submission_id) và index
    op.add_column('anchor_leaf', sa.Column('record_seq', sa.BigInteger(), nullable=False))
    op.create_foreign_key('anchor_leaf_record_seq_fkey', 'anchor_leaf', 'log_record', ['record_seq'], ['seq'])
    op.create_unique_constraint('anchor_leaf_anchor_id_record_seq_key', 'anchor_leaf', ['anchor_id', 'record_seq'])
    op.create_index(op.f('ix_anchor_leaf_record_seq'), 'anchor_leaf', ['record_seq'], unique=False)

    # F6: log_record chỉ ghi thêm
    body = (f"EXECUTE 'GRANT SELECT, INSERT ON log_record TO {APP_ROLE}'; "
            f"EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE log_record_seq TO {APP_ROLE}';")
    op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN {body} END IF; END $$")


def _backfill(bind) -> None:
    events = []  # (thời điểm, thứ tự loại, loại, dòng)
    for f in bind.execute(sa.text(
            "SELECT f.id, f.file_hash, f.hashed_at, f.baseline_file_id, f.result, s.type, s.case_id, s.owner_id "
            "FROM file_hash f JOIN submission s ON s.id = f.submission_id")).mappings():
        events.append((datetime.fromisoformat(f["hashed_at"]), 0, "file", f))
    for d in bind.execute(sa.text("SELECT id, case_id, catalog_hash, created_by, created_at FROM dossier")).mappings():
        events.append((d["created_at"], 1, "dossier", d))
    for a in bind.execute(sa.text(
            "SELECT a.id, a.file_id, a.file_hash, a.result, a.recorded_by, a.recorded_at, s.case_id "
            "FROM appraisal_step a JOIN file_hash f ON f.id = a.file_id "
            "JOIN submission s ON s.id = f.submission_id")).mappings():
        events.append((a["recorded_at"], 2, "step", a))
    for c in bind.execute(sa.text(
            "SELECT c.id, c.target, c.file_id, c.dossier_id, c.result, c.checked_by, c.checked_at, "
            "COALESCE(f.file_hash, s.bundle_hash, d.catalog_hash) AS ref_hash, "
            "COALESCE(fs.case_id, s.case_id, d.case_id, ("
            "  SELECT p.case_id FROM case_participant p JOIN case_participant k ON k.case_id = p.case_id "
            "  JOIN court_case cc ON cc.id = p.case_id "
            "  WHERE p.user_id = fs.owner_id AND k.user_id = c.checked_by AND k.role_in_case = 'CLERK' "
            "  ORDER BY cc.case_number LIMIT 1)) AS case_id "
            "FROM integrity_check c LEFT JOIN file_hash f ON f.id = c.file_id "
            "LEFT JOIN submission fs ON fs.id = f.submission_id LEFT JOIN submission s ON s.id = c.submission_id "
            "LEFT JOIN dossier d ON d.id = c.dossier_id")).mappings():
        events.append((c["checked_at"], 3, "check", c))
    events.sort(key=lambda e: (e[0], e[1]))

    seq_of, prev, seq = {}, "0" * 64, 0
    for when, _, kind, row in events:
        seq += 1
        ts = int(when.timestamp())
        if kind == "file":
            is_lot = row["type"] == "COURT_LOT"
            fields = (2 if is_lot else 1, row["file_hash"], row["case_id"], row["owner_id"],
                      RESULT_CODES[row["result"]] if is_lot else 0,
                      seq_of.get(("file", row["baseline_file_id"])) if is_lot else None)
        elif kind == "dossier":
            fields = (4, row["catalog_hash"], row["case_id"], row["created_by"], 0, None)
        elif kind == "step":
            fields = (3, row["file_hash"], row["case_id"], row["recorded_by"], RESULT_CODES[row["result"]],
                      seq_of.get(("file", row["file_id"])))
        else:
            ref = seq_of.get(("file", row["file_id"])) or seq_of.get(("dossier", row["dossier_id"]))
            fields = (2, row["ref_hash"], row["case_id"], row["checked_by"], RESULT_CODES[row["result"]], ref)
        event_type, file_hash, case_id, actor_id, result, ref_seq = fields
        raw = _encode(seq, event_type, file_hash, case_id, actor_id, ts, result, ref_seq, prev)
        record_hash = hashlib.sha256(raw).hexdigest()
        bind.execute(sa.text(
            "INSERT INTO log_record (seq, event_type, file_hash, case_id, actor_id, ts, result, ref_seq, "
            "prev_record_hash, record_hash, raw) VALUES (:seq, :event_type, :file_hash, :case_id, :actor_id, :ts, "
            ":result, :ref_seq, :prev, :record_hash, :raw)"),
            {"seq": seq, "event_type": event_type, "file_hash": file_hash, "case_id": case_id, "actor_id": actor_id,
             "ts": ts, "result": result, "ref_seq": ref_seq, "prev": prev, "record_hash": record_hash, "raw": raw})
        table = {"file": "file_hash", "dossier": "dossier", "step": "appraisal_step", "check": "integrity_check"}[kind]
        bind.execute(sa.text(f"UPDATE {table} SET record_seq = :seq WHERE id = :id"), {"seq": seq, "id": row["id"]})
        seq_of[(kind, row["id"])] = seq
        prev = record_hash
    if seq:
        bind.execute(sa.text("SELECT setval('log_record_seq', :n)"), {"n": seq})


def downgrade() -> None:
    op.execute("DELETE FROM anchor_leaf")
    op.execute("DELETE FROM anchor")
    op.drop_index(op.f('ix_anchor_leaf_record_seq'), table_name='anchor_leaf')
    op.drop_column('anchor_leaf', 'record_seq')
    op.add_column('anchor_leaf', sa.Column('submission_id', sa.UUID(), nullable=False))
    op.create_foreign_key('anchor_leaf_submission_id_fkey', 'anchor_leaf', 'submission', ['submission_id'], ['id'])
    op.create_unique_constraint('anchor_leaf_anchor_id_submission_id_key', 'anchor_leaf',
                                ['anchor_id', 'submission_id'])
    op.create_index(op.f('ix_anchor_leaf_submission_id'), 'anchor_leaf', ['submission_id'], unique=False)
    for table in LINKED_TABLES:
        op.drop_column(table, 'record_seq')
    op.drop_index(op.f('ix_log_record_file_hash'), table_name='log_record')
    op.drop_index(op.f('ix_log_record_case_id'), table_name='log_record')
    op.drop_table('log_record')
    op.execute("DROP SEQUENCE IF EXISTS log_record_seq")
