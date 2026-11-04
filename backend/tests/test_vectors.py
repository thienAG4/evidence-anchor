"""Kiểm tra theo docs/test-vectors.json (Doc 3).

Mỗi nhóm kiểm 2 lần:
1. Code của hệ thống (app.core.*) phải ra đúng kết quả trong file.
2. Cài lại độc lập chỉ bằng hashlib, theo đúng phần "formula" trong file: công thức mô tả đủ rõ để
   người ngoài (bên kiểm tra, ngôn ngữ khác) tự làm lại được.
"""
import copy
import hashlib
import io
import json
import sys
from pathlib import Path

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.hashing import compute_bundle, compute_lot_bundle, hash_stream, leaf_hash  # noqa: E402
from app.core.merkle import build_tree, verify_proof  # noqa: E402
from app.core.signing import sign_receipt, signed_message, verify_signature  # noqa: E402

VECTORS = json.loads((BACKEND_DIR.parent / "docs" / "test-vectors.json").read_text(encoding="utf-8"))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def concat(*hex_hashes: str) -> str:
    return sha(b"".join(bytes.fromhex(h) for h in hex_hashes))


def input_bytes(spec: dict) -> bytes:
    return {"utf8": lambda: spec["value"].encode("utf-8"), "hex": lambda: bytes.fromhex(spec["value"]),
            "repeat": lambda: bytes([spec["byte"]]) * spec["length"]}[spec["kind"]]()


# ---------------------------------------------------------------- SHA-256 file

@pytest.mark.parametrize("case", VECTORS["sha256_file"], ids=lambda c: c["name"])
def test_sha256_file(case):
    data = input_bytes(case["input"])
    assert len(data) == case["length"]
    assert hash_stream(io.BytesIO(data)) == case["sha256"]  # code hệ thống, đọc theo khúc 1 MB
    assert sha(data) == case["sha256"]  # băm cả file một lần


def test_sha256_nist_known_values():
    """Neo vào giá trị chuẩn công khai, phòng khi file vector bị sinh sai."""
    by_name = {c["name"]: c["sha256"] for c in VECTORS["sha256_file"]}
    assert by_name["file rỗng"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert by_name["chuỗi abc (vector chuẩn NIST)"] == \
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


# ---------------------------------------------------------------- Lá của từng file

@pytest.mark.parametrize("case", VECTORS["file_leaf"]["cases"])
def test_file_leaf(case):
    assert leaf_hash(case["fileHash"], case["hashedAt"]) == {"timeHash": case["timeHash"], "leafHash": case["leafHash"]}
    time_hash = sha(case["hashedAt"].encode("utf-8"))
    assert time_hash == case["timeHash"]
    assert concat(case["fileHash"], time_hash) == case["leafHash"]


# ---------------------------------------------------------------- Bundle

def independent_habc(files: list[dict]) -> tuple[list[str], str]:
    leaves = []
    for f in files:
        time_hash = sha(f["hashedAt"].encode("utf-8"))
        leaves.append((f["fileHash"], concat(f["fileHash"], time_hash)))
    leaves.sort(reverse=True)  # theo (fileHash, leafHash) giảm dần
    return [h for h, _ in leaves], concat(*(leaf for _, leaf in leaves))


@pytest.mark.parametrize("case", VECTORS["bundle_per_file_time_v2"]["cases"], ids=lambda c: c["name"])
def test_bundle_per_file_time_v2(case):
    exp = case["expected"]
    assert compute_bundle(case["files"], case["bundledAt"]) == exp
    order, habc = independent_habc(case["files"])
    assert order == exp["order"] and habc == exp["habc"]
    assert concat(habc, sha(case["bundledAt"].encode("utf-8"))) == exp["bundleHash"]


def test_bundle_order_independent():
    """Đổi thứ tự file đưa vào không đổi bundle."""
    case = VECTORS["bundle_per_file_time_v2"]["cases"][1]
    reversed_files = list(reversed(case["files"]))
    assert compute_bundle(reversed_files, case["bundledAt"])["bundleHash"] == case["expected"]["bundleHash"]


def test_bundle_detects_changed_time():
    case = VECTORS["bundle_per_file_time_v2"]["cases"][1]
    files = copy.deepcopy(case["files"])
    files[0]["hashedAt"] = "2020-01-01T00:00:00.00+07:00"
    assert compute_bundle(files, case["bundledAt"])["bundleHash"] != case["expected"]["bundleHash"]


@pytest.mark.parametrize("case", VECTORS["bundle_court_lot_v1"]["cases"], ids=lambda c: c["name"])
def test_bundle_court_lot_v1(case):
    exp = case["expected"]
    assert compute_lot_bundle(case["files"], case["bundledAt"], case["place"], case["fileCount"]) == exp
    _, habc = independent_habc(case["files"])
    meta = sha(f"{case['place']}|{case['fileCount']}".encode("utf-8"))
    assert meta == exp["lotMetaHash"]
    assert concat(habc, sha(case["bundledAt"].encode("utf-8")), meta) == exp["bundleHash"]


def test_lot_bundle_changes_with_place_and_count():
    hashes = {c["expected"]["bundleHash"] for c in VECTORS["bundle_court_lot_v1"]["cases"]}
    assert len(hashes) == len(VECTORS["bundle_court_lot_v1"]["cases"])


# ---------------------------------------------------------------- Merkle

def node(left: str, right: str) -> str:
    return sha(b"\x01" + bytes.fromhex(left) + bytes.fromhex(right))


def independent_root(leaves: list[str]) -> str:
    level = list(leaves)
    while len(level) > 1:
        nxt = [node(level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0]


@pytest.mark.parametrize("case", VECTORS["merkle"]["cases"], ids=lambda c: c["name"])
def test_merkle(case):
    root, proofs = build_tree(case["leaves"])
    assert root == case["root"] and proofs == case["proofs"]
    assert independent_root(case["leaves"]) == case["root"]
    for leaf, proof in zip(case["leaves"], case["proofs"]):
        assert verify_proof(leaf, proof, case["root"])
        current = leaf  # đi theo đường dẫn bằng tay
        for step in proof:
            current = node(step["hash"], current) if step["side"] == "L" else node(current, step["hash"])
        assert current == case["root"]


def test_merkle_proof_rejects_other_leaf():
    case = VECTORS["merkle"]["cases"][3]  # 5 lá
    assert not verify_proof(case["leaves"][1], case["proofs"][0], case["root"])


# ---------------------------------------------------------------- Chữ ký biên nhận (EIP-191)

SIG = VECTORS["receipt_signature_eip191"]["case"]


def test_signed_message_layout():
    message = bytes.fromhex(SIG["signedMessage"])
    assert len(message) == 58
    assert message[:16] == b"EVCHAIN-RECEIPT1"
    assert int.from_bytes(message[16:18], "big") == SIG["keyNo"]
    assert int.from_bytes(message[18:26], "big") == SIG["seq"]
    assert message[26:].hex() == SIG["receiptDigest"] == sha(SIG["canonicalJson"].encode("utf-8"))
    assert signed_message(SIG["keyNo"], SIG["seq"], SIG["receipt"]).hex() == SIG["signedMessage"]


def test_canonical_json():
    canonical = json.dumps(SIG["receipt"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert canonical == SIG["canonicalJson"]


def test_signature():
    assert sign_receipt(SIG["privateKey"], SIG["keyNo"], SIG["seq"], SIG["receipt"]) == SIG["signature"]
    assert verify_signature(SIG["address"], SIG["keyNo"], SIG["seq"], SIG["receipt"], SIG["signature"])
    # Khôi phục địa chỉ bằng thư viện ngoài, không qua code hệ thống
    recovered = Account.recover_message(encode_defunct(primitive=bytes.fromhex(SIG["signedMessage"])),
                                        signature=bytes.fromhex(SIG["signature"][2:]))
    assert recovered == SIG["address"]


@pytest.mark.parametrize("field,value", [("receiptCode", "TX-0043"), ("submittedAt", "2020-01-01T00:00:00.00+07:00")])
def test_signature_rejects_tampered_receipt(field, value):
    tampered = copy.deepcopy(SIG["receipt"])
    tampered[field] = value
    assert not verify_signature(SIG["address"], SIG["keyNo"], SIG["seq"], tampered, SIG["signature"])


def test_signature_rejects_wrong_seq_and_key():
    assert not verify_signature(SIG["address"], SIG["keyNo"], SIG["seq"] + 1, SIG["receipt"], SIG["signature"])
    assert not verify_signature(SIG["address"], SIG["keyNo"] + 1, SIG["seq"], SIG["receipt"], SIG["signature"])
