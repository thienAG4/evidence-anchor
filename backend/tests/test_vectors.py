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

import uuid

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.hashing import compute_bundle, compute_lot_bundle, hash_stream, leaf_hash  # noqa: E402
from app.core.merkle import build_tree, build_two_level, verify_proof, verify_record_proof  # noqa: E402
from app.core.record import EventType, Record, RecordError, Result, decode, verify_chain  # noqa: E402
from app.core.signing import build_signed_message, sign_receipt, signed_message, verify_signature  # noqa: E402

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


@pytest.mark.parametrize("case", VECTORS["merkle_bundle_legacy"]["cases"], ids=lambda c: c["name"])
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
    case = VECTORS["merkle_bundle_legacy"]["cases"][3]  # 5 lá
    assert not verify_proof(case["leaves"][1], case["proofs"][0], case["root"])


# ---------------------------------------------------------------- Chữ ký biên nhận (EIP-191)

SIG_GROUP = VECTORS["receipt_signature_eip191"]
SIG = SIG_GROUP["case"]


def check_signed_message_layout(message: bytes, key_id: int, seq: int, record_hash_hex: str):
    """Bố cục 58 byte theo tab 1026_Tech mục 6.5, tách bằng tay."""
    assert len(message) == 58
    assert message[:14] == b"EVC-RECEIPT-v1"
    assert int.from_bytes(message[14:18], "big") == key_id
    assert int.from_bytes(message[18:26], "big") == seq
    assert message[26:].hex() == record_hash_hex


def recover(message_hex: str, signature: str) -> str:
    """Khôi phục địa chỉ bằng thư viện ngoài, không qua code hệ thống."""
    return Account.recover_message(encode_defunct(primitive=bytes.fromhex(message_hex)),
                                   signature=bytes.fromhex(signature[2:]))


def test_signed_message_layout():
    check_signed_message_layout(bytes.fromhex(SIG["signedMessage"]), SIG["keyId"], SIG["seq"], SIG["recordHash"])
    assert SIG["recordHash"] == sha(SIG["canonicalJson"].encode("utf-8"))
    assert signed_message(SIG["keyId"], SIG["seq"], SIG["receipt"]).hex() == SIG["signedMessage"]


def test_canonical_json():
    canonical = json.dumps(SIG["receipt"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert canonical == SIG["canonicalJson"]


def test_signature():
    assert sign_receipt(SIG_GROUP["privateKey"], SIG["keyId"], SIG["seq"], SIG["receipt"]) == SIG["signature"]
    assert verify_signature(SIG_GROUP["address"], SIG["keyId"], SIG["seq"], SIG["receipt"], SIG["signature"])
    assert recover(SIG["signedMessage"], SIG["signature"]) == SIG_GROUP["address"]


@pytest.mark.parametrize("field,value", [("receiptCode", "TX-0043"), ("submittedAt", "2020-01-01T00:00:00.00+07:00")])
def test_signature_rejects_tampered_receipt(field, value):
    tampered = copy.deepcopy(SIG["receipt"])
    tampered[field] = value
    assert not verify_signature(SIG_GROUP["address"], SIG["keyId"], SIG["seq"], tampered, SIG["signature"])


def test_signature_rejects_wrong_seq_and_key():
    addr = SIG_GROUP["address"]
    assert not verify_signature(addr, SIG["keyId"], SIG["seq"] + 1, SIG["receipt"], SIG["signature"])
    assert not verify_signature(addr, SIG["keyId"] + 1, SIG["seq"], SIG["receipt"], SIG["signature"])


# ---------------------------------------------------------------- Bản ghi 164 byte (Thẻ 22 phần 2)

RECORDS = VECTORS["record_164"]["cases"]


def independent_encode(f: dict) -> bytes:
    """Ghép tay theo bảng bố cục, không dùng struct hay code hệ thống."""
    return (b"EVC-REC-v1" + f["seq"].to_bytes(8, "big") + bytes([f["typeByte"]]) + bytes.fromhex(f["fileHash"])
            + bytes.fromhex(f["caseRef"]) + bytes.fromhex(f["actorRef"]) + f["ts"].to_bytes(8, "big")
            + bytes([f["result"]]) + f["refSeq"].to_bytes(8, "big") + bytes.fromhex(f["prevRecordHash"]))


def to_record(f: dict) -> Record:
    return Record(f["seq"], EventType[f["type"]], bytes.fromhex(f["fileHash"]), bytes.fromhex(f["caseRef"]),
                  bytes.fromhex(f["actorRef"]), f["ts"], Result(f["result"]), f["refSeq"],
                  bytes.fromhex(f["prevRecordHash"]))


@pytest.mark.parametrize("case", RECORDS, ids=lambda c: f"seq{c['fields']['seq']}-{c['fields']['type']}")
def test_record_164(case):
    raw = independent_encode(case["fields"])
    assert len(raw) == case["length"] == 164
    assert raw.hex() == case["hex"]
    assert to_record(case["fields"]).encode().hex() == case["hex"]
    assert sha(raw) == case["recordHash"] == to_record(case["fields"]).record_hash().hex()
    assert decode(raw) == to_record(case["fields"])


def test_record_refs():
    """UserID / mã vụ án = UUID 16 byte + 16 byte 0; loại A không có vụ án."""
    actors = VECTORS["record_164"]["actors"]
    first = RECORDS[0]["fields"]
    assert first["actorRef"] == uuid.UUID(actors["Minh"]).bytes.hex() + "00" * 16
    assert first["caseRef"] == "00" * 32
    assert RECORDS[3]["fields"]["caseRef"] == uuid.UUID(actors["vụ án"]).bytes.hex() + "00" * 16


@pytest.mark.parametrize("case", VECTORS["must_reject"], ids=lambda c: c["name"])
def test_must_reject(case):
    with pytest.raises(RecordError):
        decode(bytes.fromhex(case["hex"]))


# ---------------------------------------------------------------- Nối chuỗi (phần 3)

def test_hash_chain():
    chain = VECTORS["hash_chain"]
    raws = [bytes.fromhex(c["hex"]) for c in RECORDS]
    assert [sha(r) for r in raws] == chain["recordHashes"]
    assert RECORDS[0]["fields"]["prevRecordHash"] == "00" * 32
    for prev, cur in zip(RECORDS, RECORDS[1:]):
        assert cur["fields"]["prevRecordHash"] == prev["recordHash"]
    assert verify_chain(raws) is None


def test_hash_chain_detects_tamper_and_gap():
    chain = VECTORS["hash_chain"]
    raws = [bytes.fromhex(c["hex"]) for c in RECORDS]
    tampered = raws[:1] + [bytes.fromhex(chain["tamperedSeq2Hex"])] + raws[2:]
    assert verify_chain(tampered) == chain["tamperedFirstBadSeq"]
    assert verify_chain(raws[:2] + raws[3:]) == 3  # thiếu seq 3


# ---------------------------------------------------------------- Merkle hai tầng (phần 4)

TWO = VECTORS["merkle_two_level"]


def leaf(record_hash_hex: str) -> str:
    return sha(bytes([0]) + bytes.fromhex(record_hash_hex))


def rfc_root(hashes: list[str]) -> str:
    """RFC 6962: tách ở lũy thừa của 2 lớn nhất nhỏ hơn n (cài lại độc lập)."""
    if len(hashes) == 1:
        return hashes[0]
    k = 1
    while k * 2 < len(hashes):
        k *= 2
    return node(rfc_root(hashes[:k]), rfc_root(hashes[k:]))


def test_merkle_two_level_independent():
    hash_of = {c["fields"]["seq"]: c["recordHash"] for c in RECORDS}
    actor_of = {c["fields"]["seq"]: c["fields"]["actorRef"] for c in RECORDS}
    groups: dict[str, list[int]] = {}
    for seq in sorted(TWO["batchSeqs"]):
        groups.setdefault(actor_of[seq], []).append(seq)
    ordered = sorted(groups.values(), key=lambda seqs: seqs[0])
    assert [g["seqs"] for g in TWO["groups"]] == ordered == [[1, 3], [2]]
    sub_roots = []
    for g, seqs in zip(TWO["groups"], ordered):
        leaves = [leaf(hash_of[s]) for s in seqs]
        assert g["leaves"] == leaves
        assert g["subRoot"] == rfc_root(leaves)
        sub_roots.append(g["subRoot"])
    assert rfc_root(sub_roots) == TWO["root"]


def test_merkle_two_level_code():
    records = [(c["fields"]["seq"], c["fields"]["actorRef"], bytes.fromhex(c["recordHash"]))
               for c in RECORDS if c["fields"]["seq"] in TWO["batchSeqs"]]
    tree = build_two_level(records)
    assert tree["root"] == TWO["root"] and tree["groups"] == TWO["groups"]
    assert {str(s): p for s, p in tree["paths"].items()} == TWO["paths"]
    for seq, _, record_hash in records:
        path = TWO["paths"][str(seq)]
        assert verify_record_proof(record_hash, path["groupPath"], path["batchPath"], TWO["root"])


# ---------------------------------------------------------------- Biên nhận seq 3 (phần 6)

REC3 = VECTORS["receipt_seq3"]


def test_receipt_seq3_signature():
    message = bytes.fromhex(REC3["signedMessage"])
    check_signed_message_layout(message, REC3["keyId"], REC3["seq"], REC3["recordHash"])
    assert build_signed_message(REC3["keyId"], REC3["seq"], bytes.fromhex(REC3["recordHash"])) == message
    assert recover(REC3["signedMessage"], REC3["signature"]) == REC3["address"]


def test_receipt_seq3_paths():
    """Biên nhận seq 3: groupPath 1 phần tử rồi batchPath 1 phần tử là ra root (như Thẻ 22)."""
    assert len(REC3["groupPath"]) == 1 and len(REC3["batchPath"]) == 1
    current = leaf(REC3["recordHash"])
    for step in REC3["groupPath"] + REC3["batchPath"]:
        current = node(step["hash"], current) if step["side"] == "L" else node(current, step["hash"])
    assert current == REC3["root"] == TWO["root"]
    assert verify_record_proof(bytes.fromhex(REC3["recordHash"]), REC3["groupPath"], REC3["batchPath"], REC3["root"])
    assert not verify_record_proof(bytes.fromhex(RECORDS[1]["recordHash"]), REC3["groupPath"], REC3["batchPath"],
                                   REC3["root"])
