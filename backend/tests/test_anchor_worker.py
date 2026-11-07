"""Worker neo với chuỗi giả (không gửi giao dịch thật), trên database test riêng.

Chạy riêng (không chung lệnh với test_vectors.py vì cần đổi DATABASE_URL trước khi nạp app):
    TEST_DATABASE_URL=postgresql+psycopg://evidence_owner:...@localhost:5434/ec_test \
        ..\\venv\\Scripts\\python.exe -m pytest tests/test_anchor_worker.py
Database phải trống; test tự chạy alembic upgrade head. Không đặt TEST_DATABASE_URL thì bỏ qua.
"""
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="cần TEST_DATABASE_URL (database test trống)")
BACKEND_DIR = Path(__file__).resolve().parent.parent
if TEST_URL:
    os.environ["DATABASE_URL"] = os.environ["MIGRATION_DATABASE_URL"] = TEST_URL
    os.environ["ANCHOR_RETRY_SECONDS"] = "0"
    sys.path.insert(0, str(BACKEND_DIR))

VN = timezone(timedelta(hours=7))


class FakeChain:
    """Đủ hàm worker cần (xem app/workers/anchor_worker.py). mine=False: giao dịch không lên khối (kẹt).
    down=True: mất mạng (phát và đọc giao dịch đều lỗi)."""

    def __init__(self):
        self.nonce, self.sent, self.mined, self.mine, self.down, self.block = 0, [], {}, True, False, 100
        self.address = "0x" + "11" * 20

    def pending_nonce(self):
        if self.down:
            raise ConnectionError("mất mạng")
        return self.nonce

    def sign(self, nonce, data, bump=0):
        tx_hash = "0x" + uuid.uuid4().hex * 2
        return tx_hash, (tx_hash, nonce, bytes(data), bump)

    def broadcast(self, raw):
        if self.down:
            raise ConnectionError("mất mạng")
        tx_hash, nonce, data, bump = raw
        self.sent.append(raw)
        if self.mine and nonce >= self.nonce:
            self.block += 1
            self.nonce = nonce + 1
            self.mined[tx_hash] = self.block

    def receipt(self, tx_hash):
        if self.down:
            raise ConnectionError("mất mạng")
        block = self.mined.get(tx_hash)
        return {"success": True, "blockNumber": block, "blockTime": 1_700_000_000} if block else None

    def finalized_block(self):
        return self.block


@pytest.fixture(scope="module")
def app_modules():
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-2000:]
    from app.db.models import AnchorBatch, AnchorState, ChainTx, LogRecord, User  # noqa: F401
    from app.db.session import SessionLocal
    from app.services import anchor_service, log_service
    from app.workers import anchor_worker
    return {"SessionLocal": SessionLocal, "anchor": anchor_service, "log": log_service, "worker": anchor_worker}


@pytest.fixture()
def env(app_modules, monkeypatch):
    """Xóa sạch dữ liệu neo và nhật ký trước mỗi test (bằng tài khoản chủ bảng), tạo 1 người ghi."""
    from sqlalchemy import text
    from app.config import settings
    from app.db.enums import UserRole
    from app.db.models import User
    db = app_modules["SessionLocal"]()
    for table in ("ots_stamp", "chain_tx_result", "chain_tx", "anchor_leaf", "anchor_batch", "file_hash", "submission",
                  "integrity_check", "appraisal_step", "dossier_item", "dossier", "log_record", "access_log",
                  "case_participant", "court_case", "user_account"):
        db.execute(text(f"DELETE FROM {table}"))
    db.execute(text("UPDATE anchor_state SET next_nonce = 0, halted = false, halted_reason = NULL, "
                    "anchor_requested_at = NULL"))
    user = User(username="w", email="w@test", full_name="Người ghi", role=UserRole.PARTY, password_hash="x")
    db.add(user)
    db.commit()
    monkeypatch.setattr(settings, "receipt_signer_address", "0x" + "22" * 20)
    chain = FakeChain()
    yield {"db": db, "user": user, "chain": chain, "settings": settings, "monkeypatch": monkeypatch, **app_modules}
    db.close()


def add(env, when: datetime, n=1):
    for _ in range(n):
        env["log"].append_record(env["db"], event_type=1, file_hash="ab" * 32, actor_id=env["user"].id,
                                 ts=int(when.timestamp()))
    env["db"].commit()


def batches(env):
    from app.db.models import AnchorBatch
    env["db"].expire_all()
    return [(b.batch_no, b.from_seq, b.to_seq) for b in env["db"].query(AnchorBatch).order_by(AnchorBatch.batch_no)]


def kinds(env):
    from app.db.models import ChainTx
    env["db"].expire_all()
    return [t.kind.value for t in env["db"].query(ChainTx).order_by(ChainTx.nonce, ChainTx.sent_at)]


def run_daily(env, now: datetime, cutoff="23:59"):
    s = env["settings"]
    env["monkeypatch"].setattr(s, "anchor_mode", "daily")
    env["monkeypatch"].setattr(s, "anchor_daily_cutoff", cutoff)
    env["monkeypatch"].setattr(env["anchor"], "_now", lambda: now.astimezone(timezone.utc))
    return env["worker"].run_once(env["chain"])


# ---------------------------------------------------------------- Chế độ theo ngày

def test_day_end_boundary(app_modules):
    day_end = app_modules["anchor"].day_end
    t2358 = datetime(2026, 11, 5, 23, 58, tzinfo=VN)
    t0001 = datetime(2026, 11, 6, 0, 1, tzinfo=VN)
    t2359 = datetime(2026, 11, 5, 23, 59, tzinfo=VN)
    assert day_end(int(t2358.timestamp()), "23:59") == int(t2359.timestamp())
    assert day_end(int(t2359.timestamp()), "23:59") == int((t2359 + timedelta(days=1)).timestamp())  # đúng mốc: ngày sau
    assert day_end(int(t0001.timestamp()), "23:59") == int((t2359 + timedelta(days=1)).timestamp())


def test_daily_waits_for_cutoff_then_one_batch(env):
    add(env, datetime(2026, 11, 5, 9, 0, tzinfo=VN), 3)
    assert run_daily(env, datetime(2026, 11, 5, 23, 0, tzinfo=VN)) == 0  # chưa tới mốc: chưa khóa
    assert batches(env) == [] and kinds(env) == ["KEYR"]
    assert run_daily(env, datetime(2026, 11, 5, 23, 59, 30, tzinfo=VN)) == 3
    assert batches(env) == [(1, 1, 3)] and kinds(env) == ["KEYR", "ANCH"]


def test_day_boundary_two_batches_ui13(env):
    add(env, datetime(2026, 11, 5, 23, 58, tzinfo=VN))
    add(env, datetime(2026, 11, 6, 0, 1, tzinfo=VN))
    run_daily(env, datetime(2026, 11, 6, 23, 59, 30, tzinfo=VN))  # qua cả hai mốc
    assert batches(env) == [(1, 1, 1), (2, 2, 2)]  # hai ngày, hai đợt, hai root


def test_catch_up_after_worker_off_ui14(env):
    for day in (3, 4, 5):  # worker tắt 3 ngày
        add(env, datetime(2026, 11, day, 10, 0, tzinfo=VN), 2)
    run_daily(env, datetime(2026, 11, 6, 8, 0, tzinfo=VN))
    assert batches(env) == [(1, 1, 2), (2, 3, 4), (3, 5, 6)]  # neo bù từng ngày, không mất bản ghi


def test_empty_day_no_anchor_ui38(env):
    assert run_daily(env, datetime(2026, 11, 5, 23, 59, 30, tzinfo=VN)) == 0
    assert batches(env) == []
    add(env, datetime(2026, 11, 3, 10, 0, tzinfo=VN))  # ngày 3 có, ngày 4 trống, ngày 5 có
    add(env, datetime(2026, 11, 5, 10, 0, tzinfo=VN))
    run_daily(env, datetime(2026, 11, 5, 23, 59, 30, tzinfo=VN))
    assert batches(env) == [(1, 1, 1), (2, 2, 2)]  # ngày trống không có đợt


def test_anchor_now_button(env):
    add(env, datetime(2026, 11, 5, 9, 0, tzinfo=VN), 2)
    env["anchor"].request_anchor_now(env["db"])
    env["anchor"].request_anchor_now(env["db"])  # bấm 2 lần: vẫn 1 yêu cầu
    assert run_daily(env, datetime(2026, 11, 5, 9, 5, tzinfo=VN)) == 2  # chưa tới 23:59 vẫn khóa
    assert batches(env) == [(1, 1, 2)]
    add(env, datetime(2026, 11, 5, 9, 10, tzinfo=VN))
    assert run_daily(env, datetime(2026, 11, 5, 9, 15, tzinfo=VN)) == 0  # yêu cầu đã dùng xong, lại đợi mốc
    assert env["anchor"].schedule(env["db"])["pendingRecords"] == 1


def test_contiguous_payloads(env):
    from app.core.payload import check_contiguous, decode_anch
    from app.db.models import AnchorBatch
    for day in (3, 4):
        add(env, datetime(2026, 11, day, 10, 0, tzinfo=VN), 3)
    run_daily(env, datetime(2026, 11, 5, 8, 0, tzinfo=VN))
    rows = env["db"].query(AnchorBatch).order_by(AnchorBatch.batch_no).all()
    a1, a2 = (decode_anch(r.payload) for r in rows)
    check_contiguous(a1, a2)


# ---------------------------------------------------------------- Lỗi mạng, giao dịch kẹt, giao dịch lạ

def test_network_down_then_resend(env):
    from app.db.enums import ChainTxKind, ChainTxStatus
    from app.db.models import ChainTx, ChainTxResult
    add(env, datetime(2026, 11, 5, 9, 0, tzinfo=VN))
    env["worker"].run_once(env["chain"])  # vòng đầu có mạng: KEYR, ANCH đợt 1
    add(env, datetime(2026, 11, 5, 9, 1, tzinfo=VN))
    env["chain"].down = True
    with pytest.raises(ConnectionError):
        env["worker"].run_once(env["chain"])  # mất mạng: vòng lỗi, worker (vòng ngoài) ghi log rồi chạy lại sau
    env["chain"].down = False
    for _ in range(3):
        env["worker"].run_once(env["chain"])
    assert batches(env) == [(1, 1, 1), (2, 2, 2)]  # không mất bản ghi
    env["db"].expire_all()
    ok = env["db"].query(ChainTx).join(ChainTxResult, ChainTxResult.tx_id == ChainTx.id).filter(
        ChainTx.kind == ChainTxKind.ANCH, ChainTxResult.status == ChainTxStatus.CONFIRMED).count()
    assert ok == 2


def test_broadcast_fails_then_replaced(env):
    """Ký và lưu giao dịch xong thì mất mạng lúc phát: lần sau gửi lại cùng nonce (không cấp nonce mới)."""
    add(env, datetime(2026, 11, 5, 9, 0, tzinfo=VN))
    real = env["chain"].broadcast
    env["chain"].broadcast = lambda raw: (_ for _ in ()).throw(ConnectionError("mất mạng lúc phát"))
    env["worker"].run_once(env["chain"])
    env["chain"].broadcast = real
    env["worker"].run_once(env["chain"])
    env["worker"].run_once(env["chain"])
    nonces = sorted({n for _, n, _, _ in env["chain"].sent})
    assert nonces == [0, 1] and batches(env) == [(1, 1, 1)]


def test_stuck_tx_replaced_then_halt(env):
    from app.db.models import AnchorState
    env["monkeypatch"].setattr(env["settings"], "anchor_max_replacements", 2)
    env["chain"].mine = False  # không giao dịch nào lên khối
    add(env, datetime(2026, 11, 5, 9, 0, tzinfo=VN))
    for _ in range(5):
        env["worker"].run_once(env["chain"])
    env["db"].expire_all()
    state = env["db"].get(AnchorState, 1)
    assert state.halted and "kẹt" in state.halted_reason
    bumps = [bump for _, nonce, data, bump in env["chain"].sent if data.startswith(b"KEYR")]
    assert bumps == [0, 1, 2]  # gửi lại cùng nonce, phí tăng, tới giới hạn thì dừng


def test_foreign_tx_halts(env):
    add(env, datetime(2026, 11, 5, 9, 0, tzinfo=VN))
    env["worker"].run_once(env["chain"])
    env["chain"].nonce += 1  # ai đó dùng ví ngoài worker
    add(env, datetime(2026, 11, 5, 9, 1, tzinfo=VN))
    env["worker"].run_once(env["chain"])
    from app.db.models import AnchorState
    env["db"].expire_all()
    state = env["db"].get(AnchorState, 1)
    assert state.halted and "vượt next_nonce" in state.halted_reason
    assert batches(env) == [(1, 1, 1)]  # bản ghi mới không vào đợt khi đang dừng


# ---------------------------------------------------------------- OpenTimestamps phía server

def _ots_submission(env):
    """Một lần lưu chứng 1 file (bản ghi A) của người ghi trong env."""
    from app.db.enums import SubmissionType
    from app.db.models import FileHash, Submission
    add(env, datetime(2026, 11, 5, 9, 0, tzinfo=VN))
    sub = Submission(receipt_code="TX-9001", type=SubmissionType.SELF, owner_id=env["user"].id, file_count=1,
                     submitted_at=datetime(2026, 11, 5, 9, 0, tzinfo=VN), bundle_scheme="x", habc="0" * 64,
                     bundled_at="x", bundle_time_hash="0" * 64, bundle_hash="0" * 64, signature="0x",
                     receipt_json={})
    env["db"].add(sub)
    env["db"].flush()
    env["db"].add(FileHash(submission_id=sub.id, position=1, file_name="a.pdf", file_code="TX-9001-1",
                           file_hash="ab" * 32, hashed_at="x", time_hash="0" * 64, leaf_hash="0" * 64, record_seq=1))
    env["db"].commit()
    return sub


def test_ots_save_pending_rules(env):
    from test_ots import CALS, browser_ots
    from app.errors.handlers import AppError
    from app.services import ots_service
    sub = _ots_submission(env)
    with pytest.raises(AppError, match="đúng hash"):
        ots_service.save_pending(env["db"], sub, "TX-9001-1", browser_ots("cd" * 32, CALS))
    with pytest.raises(AppError, match="cho phép"):  # job nâng cấp sẽ gọi địa chỉ trong file: chặn địa chỉ lạ
        ots_service.save_pending(env["db"], sub, "TX-9001-1", browser_ots("ab" * 32, ["http://127.0.0.1:5434/"]))
    with pytest.raises(AppError):
        ots_service.save_pending(env["db"], sub, "TX-9001-1", b"rac")
    ots_service.save_pending(env["db"], sub, "TX-9001-1", browser_ots("ab" * 32, CALS))
    with pytest.raises(AppError, match="đã có"):
        ots_service.save_pending(env["db"], sub, "TX-9001-1", browser_ots("ab" * 32, CALS))
    assert ots_service.view(env["db"], sub)[0]["status"] == "PENDING"


def test_ots_upgrade_and_alarm(env, caplog):
    from test_ots import CALS, browser_ots
    from app.db.models import OtsStamp
    from app.services import ots_service
    sub = _ots_submission(env)
    ots_service.save_pending(env["db"], sub, "TX-9001-1", browser_ots("ab" * 32, CALS))
    later = datetime.now(timezone.utc) + timedelta(hours=49)
    still_pending = lambda data: (data, False)  # noqa: E731
    with caplog.at_level("ERROR"):
        assert ots_service.upgrade_pending(env["db"], later, upgrade=still_pending) ==             {"upgraded": 0, "pending": 1, "late": 1}
    assert "chưa xác nhận sau 48 giờ" in caplog.text
    complete = browser_ots("ab" * 32, CALS[:1], height=870001)
    assert ots_service.upgrade_pending(env["db"], later, upgrade=lambda data: (complete, True))["upgraded"] == 1
    env["db"].expire_all()
    stamp = env["db"].query(OtsStamp).one()
    assert stamp.bitcoin_block == 870001 and stamp.ots_pending != stamp.ots_complete  # bản chờ giữ nguyên
    view = ots_service.view(env["db"], sub)[0]
    assert view["status"] == "COMPLETE" and view["bitcoinBlock"] == 870001
