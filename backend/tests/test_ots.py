"""OpenTimestamps: file .ots theo đúng cách trình duyệt ghép (assets/js/data/ots.js) đọc được bằng thư viện chuẩn;
/verify kiểm offline. Không gọi mạng: phản hồi máy chủ lịch được dựng giả bằng chính thư viện opentimestamps."""
import base64
import hashlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation  # noqa: E402
from opentimestamps.core.op import OpAppend, OpSHA256  # noqa: E402
from opentimestamps.core.serialize import BytesSerializationContext  # noqa: E402
from opentimestamps.core.timestamp import Timestamp  # noqa: E402

from app.core import ots  # noqa: E402

MAGIC = bytes.fromhex("004f70656e54696d657374616d7073000050726f6f6600bf89e2e884e89294")
FILE_HASH = hashlib.sha256(b"hop dong").hexdigest()


def calendar_answer(msg: bytes, uri: str, height: int | None = None) -> bytes:
    """Phản hồi kiểu máy chủ lịch: một nhánh từ msg tới PendingAttestation (hoặc block Bitcoin nếu có height)."""
    ts = Timestamp(msg)
    tip = ts.ops.add(OpAppend(os.urandom(8))).ops.add(OpSHA256())
    tip.attestations.add(BitcoinBlockHeaderAttestation(height) if height else PendingAttestation(uri))
    ctx = BytesSerializationContext()
    ts.serialize(ctx)
    return ctx.getbytes()


def browser_ots(file_hash: str, uris, height=None) -> bytes:
    """Ghép y như ots.js: magic ‖ 01 ‖ 08 ‖ fileHash ‖ nhánh (ff ‖ ...) ‖ nhánh cuối."""
    fh = bytes.fromhex(file_hash)
    branches = []
    for uri in uris:
        nonce = os.urandom(16)
        digest = hashlib.sha256(fh + nonce).digest()
        branches.append(b"\xf0\x10" + nonce + b"\x08" + calendar_answer(digest, uri, height))
    body = b"".join(b"\xff" + b for b in branches[:-1]) + branches[-1]
    return MAGIC + b"\x01\x08" + fh + body


CALS = ["https://alice.btc.calendar.opentimestamps.org", "https://finney.calendar.eternitywall.com"]


def test_browser_format_reads_with_library():
    meta = ots.info(browser_ots(FILE_HASH, CALS))
    assert meta.file_hash == FILE_HASH
    assert meta.pending_calendars == tuple(sorted(CALS)) and not meta.complete


def test_single_calendar_and_complete():
    meta = ots.info(browser_ots(FILE_HASH, CALS[:1], height=870000))
    assert meta.complete and meta.bitcoin_blocks == (870000,)


@pytest.mark.parametrize("data", [b"", MAGIC, b"\x00" * 80, browser_ots(FILE_HASH, CALS)[:-5],
                                  browser_ots(FILE_HASH, CALS) + b"\x00"], ids=["rỗng", "chỉ magic", "rác",
                                                                               "cụt", "thừa byte"])
def test_must_reject(data):
    with pytest.raises(ots.OtsError):
        ots.info(data)


def test_verify_offline_check():
    from app.services.verify_service import _check_ots
    checks = []

    def check(name, ok, detail=None):
        checks.append((name, ok, detail))

    files = [{"fileCode": "TX-1-1", "fileHash": FILE_HASH}, {"fileCode": "TX-1-2", "fileHash": "ab" * 32}]
    good = {"fileCode": "TX-1-1", "ots": base64.b64encode(browser_ots(FILE_HASH, CALS)).decode()}
    _check_ots(check, files, [good])
    assert checks[-1][1] and "đang chờ" in checks[-1][2] and "opentimestamps.org" in checks[-1][2]
    wrong = {"fileCode": "TX-1-2", "ots": good["ots"]}  # .ots của file khác
    _check_ots(check, files, [good, wrong])
    assert not checks[-1][1] and "TX-1-2" in checks[-1][2]
    _check_ots(check, files, [])  # không có OTS: không thêm mục kiểm, không làm biên nhận sai
    assert len(checks) == 2
