"""Sinh docs/test-vectors.json: đầu vào cố định + kết quả đúng cho hash, bundle, Merkle, chữ ký biên nhận.

Chạy (từ gốc repo): venv\\Scripts\\python.exe backend/scripts/gen_test_vectors.py
Kiểm tra lại:       venv\\Scripts\\python.exe -m pytest backend/tests/test_vectors.py

Mục đích: ai viết lại thuật toán (ngôn ngữ khác, bên kiểm tra độc lập) chỉ cần ra đúng các kết quả này.
Chỉ chạy lại script khi CỐ Ý đổi công thức; khi đó tăng "version" và ghi lý do vào commit.
"""
import hashlib
import io
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.hashing import (BUNDLE_SCHEME, LOT_SCHEME, CHUNK_SIZE, compute_bundle, compute_lot_bundle, hash_stream,
                              leaf_hash, lot_meta_hash)
import uuid

from app.core.anchor_payload import encode_keyr, encode_noop
from app.core.merkle import build_tree, build_two_level, record_leaf
from app.core.payload import Anch
from app.core.record import ZERO32, EventType, Record, Result, ref32
from app.core.signing import build_signed_message, canonical_json, sign_receipt, signed_message, signer_address
from eth_account import Account
from eth_account.messages import encode_defunct

OUTPUT = BACKEND_DIR.parent / "docs" / "test-vectors.json"

# Khóa test CÔNG KHAI (tài khoản #0 mặc định của Hardhat/Anvil): ai cũng biết, KHÔNG có tiền thật, KHÔNG dùng thật.
TEST_SIGNING_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_input_bytes(spec: dict) -> bytes:
    """Mô tả đầu vào gọn trong JSON: utf8 / hex / lặp 1 byte n lần (file lớn)."""
    if spec["kind"] == "utf8":
        return spec["value"].encode("utf-8")
    if spec["kind"] == "hex":
        return bytes.fromhex(spec["value"])
    if spec["kind"] == "repeat":
        return bytes([spec["byte"]]) * spec["length"]
    raise ValueError(spec["kind"])


def sha256_file_vectors() -> list[dict]:
    specs = [
        ("file rỗng", {"kind": "utf8", "value": ""}),
        ("chuỗi abc (vector chuẩn NIST)", {"kind": "utf8", "value": "abc"}),
        ("tiếng Việt UTF-8", {"kind": "utf8", "value": "Hợp đồng vay tiền"}),
        ("đúng 1 khúc đọc (1 MB, byte 0x61)", {"kind": "repeat", "byte": 0x61, "length": CHUNK_SIZE}),
        ("1 khúc + 1 byte (1 MB + 1)", {"kind": "repeat", "byte": 0x61, "length": CHUNK_SIZE + 1}),
    ]
    out = []
    for name, spec in specs:
        data = file_input_bytes(spec)
        assert hash_stream(io.BytesIO(data)) == sha256_hex(data)
        out.append({"name": name, "input": spec, "length": len(data), "sha256": sha256_hex(data)})
    return out


H_HOP_DONG = sha256_hex("hop_dong_vay".encode())
H_ANH = sha256_hex("anh_chuyen_khoan".encode())
H_GHI_AM = sha256_hex("ghi_am_cuoc_goi".encode())


def leaf_vectors() -> list[dict]:
    cases = [(H_HOP_DONG, "2026-11-04T21:05:35.16+07:00"), (H_ANH, "2026-11-04T21:05:37.42+07:00")]
    return [{"fileHash": h, "hashedAt": t, **leaf_hash(h, t)} for h, t in cases]


def bundle_vectors() -> list[dict]:
    three = [  # cố ý KHÔNG theo thứ tự: công thức phải tự sắp lá theo fileHash giảm dần
        {"fileHash": H_ANH, "hashedAt": "2026-11-04T21:05:37.42+07:00"},
        {"fileHash": H_HOP_DONG, "hashedAt": "2026-11-04T21:05:35.16+07:00"},
        {"fileHash": H_GHI_AM, "hashedAt": "2026-11-04T21:05:39.87+07:00"},
    ]
    cases = [
        ("1 file", three[1:2], "2026-11-04T21:05:35.16+07:00"),
        ("3 file đưa vào lộn thứ tự", three, "2026-11-04T21:05:39.87+07:00"),
        ("2 file trùng nội dung, khác giờ băm", [
            {"fileHash": H_ANH, "hashedAt": "2026-11-04T21:10:00.00+07:00"},
            {"fileHash": H_ANH, "hashedAt": "2026-11-04T21:10:02.50+07:00"},
        ], "2026-11-04T21:10:02.50+07:00"),
    ]
    return [{"name": name, "files": files, "bundledAt": at, "expected": compute_bundle(files, at)}
            for name, files, at in cases]


def lot_vectors() -> list[dict]:
    files = [
        {"fileHash": H_HOP_DONG, "hashedAt": "2026-11-05T09:30:15.04+07:00"},
        {"fileHash": H_GHI_AM, "hashedAt": "2026-11-05T09:30:17.90+07:00"},
    ]
    at, place = "2026-11-05T09:30:17.90+07:00", "TAND Quận 1, TP.HCM"
    out = []
    for name, p, n in [("lô 2 file", place, 2), ("cùng file, đổi nơi nộp", "TAND Quận 3, TP.HCM", 2),
                       ("cùng file, khai sai số lượng", place, 3)]:
        assert lot_meta_hash(p, n) == sha256_hex(f"{p}|{n}".encode())
        out.append({"name": name, "files": files, "bundledAt": at, "place": p, "fileCount": n,
                    "expected": compute_lot_bundle(files, at, p, n)})
    return out


def merkle_vectors() -> list[dict]:
    out = []
    for n in (1, 2, 3, 5, 7):
        leaves = [sha256_hex(f"bundle-{i}".encode()) for i in range(n)]
        root, proofs = build_tree(leaves)
        out.append({"name": f"{n} lá", "leaves": leaves, "root": root, "proofs": proofs})
    return out


def eip191_sign(message: bytes) -> str:
    signed = Account.sign_message(encode_defunct(primitive=message), private_key=TEST_SIGNING_KEY)
    return "0x" + signed.signature.hex().removeprefix("0x")


def interim_receipt_signature_vector() -> dict:
    """Cách hệ thống đang ký TRƯỚC khi có bản ghi 164 byte: recordHash tạm = SHA256(biên nhận JSON)."""
    receipt = {"receiptCode": "TX-0042", "type": "SELF", "submittedAt": "2026-11-04T21:05:35.16+07:00",
               "bundle": {"bundleHash": sha256_hex(b"bundle-demo")},
               "signer": {"algorithm": "EIP-191", "keyNo": 1, "address": signer_address(TEST_SIGNING_KEY)}}
    key_id, seq = 1, 42
    return {
        "name": "tạm: recordHash = SHA256(biên nhận JSON), seq = số của mã biên nhận",
        "keyId": key_id,
        "seq": seq,
        "receipt": receipt,
        "canonicalJson": canonical_json(receipt).decode("utf-8"),
        "recordHash": sha256_hex(canonical_json(receipt)),
        "signedMessage": signed_message(key_id, seq, receipt).hex(),
        "signature": sign_receipt(TEST_SIGNING_KEY, key_id, seq, receipt),
    }


# ---------------------------------------------------------------- Bản ghi 164 byte (Thẻ 22, phần 2-4, 6)
# Kịch bản: Minh lưu chứng (seq 1), Lan lưu chứng (seq 2), Minh lưu chứng (seq 3) -> một đợt, hai nhóm.
# Sau đó thư ký đối chiếu file của Minh (E, seq 4, trỏ về seq 1) rồi gửi giám định (C, seq 5, trỏ về seq 4).
MINH = uuid.UUID("11111111-1111-4111-8111-111111111111")
LAN = uuid.UUID("22222222-2222-4222-8222-222222222222")
THU_KY = uuid.UUID("33333333-3333-4333-8333-333333333333")
VU_AN = uuid.UUID("44444444-4444-4444-8444-444444444444")
TS0 = 1793800000  # 2026-11-04T23:26:40+07:00


def demo_records() -> list[Record]:
    specs = [
        (EventType.A, H_HOP_DONG, None, MINH, TS0, Result.NOT_APPLICABLE, 0),
        (EventType.A, H_ANH, None, LAN, TS0 + 60, Result.NOT_APPLICABLE, 0),
        (EventType.A, H_GHI_AM, None, MINH, TS0 + 120, Result.NOT_APPLICABLE, 0),
        (EventType.E, H_HOP_DONG, VU_AN, THU_KY, TS0 + 86400, Result.MATCH, 1),
        (EventType.C, H_HOP_DONG, VU_AN, THU_KY, TS0 + 2 * 86400, Result.MATCH, 4),
    ]
    records, prev = [], ZERO32
    for seq, (type_, file_hash, case, actor, ts, result, ref_seq) in enumerate(specs, 1):
        record = Record(seq, type_, bytes.fromhex(file_hash), ref32(case), ref32(actor), ts, result, ref_seq, prev)
        records.append(record)
        prev = record.record_hash()
    return records


def record_view(record: Record) -> dict:
    return {
        "fields": {"seq": record.seq, "type": record.type.name, "typeByte": int(record.type),
                   "fileHash": record.file_hash.hex(), "caseRef": record.case_ref.hex(),
                   "actorRef": record.actor_ref.hex(), "ts": record.ts, "result": int(record.result),
                   "refSeq": record.ref_seq, "prevRecordHash": record.prev_record_hash.hex()},
        "hex": record.encode().hex(),
        "length": len(record.encode()),
        "recordHash": record.record_hash().hex(),
    }


def record_vectors() -> dict:
    records = demo_records()
    batch = records[:3]  # đợt 1: seq 1-3 (chỉ bản ghi lưu chứng)
    tree = build_two_level([(r.seq, r.actor_ref.hex(), r.record_hash()) for r in batch])
    seq3 = records[2]
    message = build_signed_message(1, seq3.seq, seq3.record_hash())
    good = records[0].encode()
    return {
        "record_164": {
            "layout": "label \"EVC-REC-v1\" 10 | seq u64 8 | type u8 1 (A=1,E=2,C=3,D=4) | fileHash 32 | caseRef 32 | "
                      "actorRef 32 | ts u64 8 (giây Unix) | result u8 1 (0 không áp dụng, 1 MATCH, 2 MISMATCH, 3 NO_A) | "
                      "refSeq u64 8 | prevRecordHash 32; big-endian; tổng 164",
            "refs": "caseRef/actorRef = UUID 16 byte + 16 byte 0 (1027_Tech: UserID, mã vụ án nội bộ, không salt); "
                    "loại A: caseRef toàn 0",
            "recordHash": "SHA256(164 byte)",
            "actors": {"Minh": str(MINH), "Lan": str(LAN), "thư ký": str(THU_KY), "vụ án": str(VU_AN)},
            "cases": [record_view(r) for r in records],
        },
        "hash_chain": {
            "rule": "seq tăng liên tục từ 1; prevRecordHash(seq n) = recordHash(seq n-1); seq 1 có prevRecordHash toàn 0",
            "recordHashes": [r.record_hash().hex() for r in records],
            "tamperedSeq2Hex": _flip_last_byte_of_file_hash(records[1]),
            "tamperedFirstBadSeq": 3,
        },
        "merkle_two_level": {
            "formula": "lá = SHA256(0x00 ‖ recordHash); trong mỗi nhóm (cùng actorRef) dựng cây RFC 6962 ra subRoot; "
                       "nhóm xếp theo seq nhỏ nhất; tầng trên dựng cây RFC 6962 trên các subRoot (đưa thẳng vào như nút, "
                       "không thêm 0x00) ra root. Nút trong = SHA256(0x01 ‖ trái ‖ phải).",
            "assumption": "Cách đưa subRoot vào tầng trên (không thêm 0x00) cần nhóm xác nhận.",
            "batchSeqs": [r.seq for r in batch],
            "groups": tree["groups"],
            "root": tree["root"],
            "paths": {str(seq): path for seq, path in tree["paths"].items()},
        },
        "receipt_seq3": {
            "formula": "signedMessage (58) = \"EVC-RECEIPT-v1\" 14 ‖ keyId u32 4 ‖ seq u64 8 ‖ recordHash 32; "
                       "chữ ký EIP-191 personal_sign trên 58 byte",
            "privateKey": TEST_SIGNING_KEY,
            "address": signer_address(TEST_SIGNING_KEY),
            "keyId": 1,
            "seq": seq3.seq,
            "recordHash": seq3.record_hash().hex(),
            "signedMessage": message.hex(),
            "signature": eip191_sign(message),
            "groupPath": tree["paths"][3]["groupPath"],
            "batchPath": tree["paths"][3]["batchPath"],
            "root": tree["root"],
        },
        "must_reject": [
            {"name": "bản ghi 163 byte", "hex": good[:163].hex(), "reason": "sai độ dài"},
            {"name": "nhãn sai EVC-REX-v1", "hex": (b"EVC-REX-v1" + good[10:]).hex(), "reason": "sai nhãn"},
            {"name": "loại sự kiện 9", "hex": (good[:18] + bytes([9]) + good[19:]).hex(), "reason": "type ngoài 1-4"},
            {"name": "kết quả 7", "hex": (good[:123] + bytes([7]) + good[124:]).hex(), "reason": "result ngoài 0-3"},
            {"name": "seq 1 có prevRecordHash khác 0", "hex": (good[:-32] + b"\x01" * 32).hex(),
             "reason": "bản ghi đầu tiên phải có prevRecordHash toàn 0"},
            {"name": "bản ghi A có caseRef khác 0", "hex": (good[:51] + b"\x01" + good[52:]).hex(),
             "reason": "loại A không có vụ án"},
        ],
    }


def _patch(raw: bytes, offset: int, value: bytes) -> str:
    return (raw[:offset] + value + raw[offset + len(value):]).hex()


def chain_line_vectors() -> dict:
    """Phần 5: dòng ANCH (93 byte, hướng A theo 1026_Tech), KEYR, NOOP."""
    root1 = bytes.fromhex(build_two_level([(r.seq, r.actor_ref.hex(), r.record_hash())
                                           for r in demo_records()[:3]])["root"])
    root2 = bytes.fromhex(sha256_hex(b"root-dot-2"))
    first, second = Anch(1, 1, 3, bytes(32), root1), Anch(2, 4, 5, root1, root2)
    good = first.encode()

    def anch_view(a: Anch) -> dict:
        return {"input": {"batchId": a.batch_no, "fromSeq": a.from_seq, "toSeq": a.to_seq,
                          "prevRoot": a.prev_root.hex(), "root": a.root.hex()},
                "hex": a.encode().hex(), "length": len(a.encode())}

    old_85 = b"ANCH" + bytes([1]) + (1).to_bytes(8, "big") + (3).to_bytes(8, "big") + bytes(32) + root1
    # offset: tag 0..3 | version 4 | batchId 5..12 | fromSeq 13..20 | toSeq 21..28 | prevRoot 29..60 | root 61..92
    anch_reject = [
        {"name": "ANCH 92 byte (thiếu byte cuối)", "hex": good[:92].hex()},
        {"name": "ANCH 85 byte kiểu cũ (recordCount)", "hex": old_85.hex()},
        {"name": "nhãn sai ANCX", "hex": _patch(good, 0, b"ANCX")},
        {"name": "phiên bản 2", "hex": _patch(good, 4, bytes([2]))},
        {"name": "đợt 1 có prevRoot khác 0", "hex": _patch(good, 29, b"\x01" * 32)},
        {"name": "đợt 1 có fromSeq khác 1", "hex": _patch(good, 13, (2).to_bytes(8, "big"))},
        {"name": "toSeq nhỏ hơn fromSeq", "hex": second.encode()[:21].hex() + (3).to_bytes(8, "big").hex()
                                                    + second.encode()[29:].hex()},
        {"name": "số đợt 0", "hex": _patch(good, 5, bytes(8))},
    ]
    s = second.encode()
    contiguity_reject = [
        {"name": "hở bản ghi: đợt 2 bắt đầu từ 5", "prev": good.hex(), "next": _patch(s, 13, (5).to_bytes(8, "big"))},
        {"name": "chồng bản ghi: đợt 2 bắt đầu từ 3", "prev": good.hex(), "next": _patch(s, 13, (3).to_bytes(8, "big"))},
        {"name": "prevRoot đợt 2 khác root đợt 1", "prev": good.hex(), "next": _patch(s, 29, root2)},
        {"name": "nhảy số đợt 1 → 3", "prev": good.hex(), "next": _patch(s, 5, (3).to_bytes(8, "big"))},
    ]

    signer = signer_address(TEST_SIGNING_KEY).lower()
    keyr = encode_keyr(1, signer, 1)
    keyr_view = {"input": {"keyId": 1, "address": signer, "fromSeq": 1}, "hex": keyr.hex(), "length": len(keyr)}
    keyr_reject = [
        {"name": "KEYR 35 byte kiểu cũ (keyNo u16)", "hex": (keyr[:5] + keyr[7:]).hex()},
        {"name": "nhãn sai KEYX", "hex": _patch(keyr, 0, b"KEYX")},
        {"name": "phiên bản 2", "hex": _patch(keyr, 4, bytes([2]))},
        {"name": "fromSeq 0", "hex": _patch(keyr, 29, bytes(8))},
    ]
    noop = encode_noop(7)
    noop_reject = [
        {"name": "NOOP 12 byte", "hex": noop[:12].hex()},
        {"name": "nhãn sai NOOX", "hex": _patch(noop, 0, b"NOOX")},
        {"name": "phiên bản 2", "hex": _patch(noop, 4, bytes([2]))},
    ]
    return {"chain_lines": {
        "common": "mọi dòng: nhãn 4 byte ASCII ‖ phiên bản u8 (=1) ‖ payload; số nguyên không dấu big-endian",
        "anch": {
            "layout": "\"ANCH\" 4 | version 1 | batchId u64 8 | fromSeq u64 8 | toSeq u64 8 | prevRoot 32 | root 32 "
                      "= 93 byte",
            "source": "1026_Tech; nhóm chốt hướng A (khoảng số thứ tự, có byte phiên bản)",
            "rules": "đợt 1: prevRoot toàn 0, fromSeq = 1; toSeq ≥ fromSeq; đợt sau: batchId +1, "
                     "prevRoot = root đợt trước, fromSeq = toSeq đợt trước + 1",
            "cases": [anch_view(first), anch_view(second)],
            "must_reject": anch_reject,
            "contiguity_must_reject": contiguity_reject,
        },
        "keyr": {
            "layout": "\"KEYR\" 4 | version 1 | keyId u32 4 | địa chỉ khóa ký 20 | fromSeq u64 8 = 37 byte",
            "note": "keyId cùng kiểu u32 với keyId trong 58 byte được ký (receipt_signature_58)",
            "cases": [keyr_view], "must_reject": keyr_reject,
        },
        "noop": {
            "layout": "\"NOOP\" 4 | version 1 | nonce u64 8 = 13 byte",
            "note": "gửi cùng nonce với giao dịch kẹt để thay nó; nonce ghi lại để đối chiếu",
            "cases": [{"input": {"nonce": 7}, "hex": noop.hex(), "length": len(noop)}], "must_reject": noop_reject,
        },
    }}


def _flip_last_byte_of_file_hash(record: Record) -> str:
    raw = bytearray(record.encode())
    raw[18 + 32] ^= 0x01  # byte cuối của fileHash (label 10 + seq 8 + type 1 = 19; fileHash 19..50)
    return bytes(raw).hex()


def build() -> dict:
    return {
        "version": "evidencechain-test-vectors-v2",
        "parts": {
            "1_che_ma": "Bỏ: 1027_Tech dùng UserID và mã vụ án nội bộ, không salt/HMAC (xem record_164.refs).",
            "2_ban_ghi_164": "record_164", "3_noi_chuoi": "hash_chain", "4_merkle_hai_tang": "merkle_two_level",
            "5_payload_anch": "chain_lines (ANCH 93 byte theo 1026_Tech, KEYR 37 byte, NOOP 13 byte)",
            "6_bien_nhan": "receipt_seq3 (đích) và receipt_signature_eip191 (cách đang chạy tạm)",
            "mau_phai_tu_choi": "must_reject",
        },
        **record_vectors(),
        **chain_line_vectors(),
        "conventions": {
            "hash": "SHA-256, viết hex chữ thường 64 ký tự",
            "concat": "‖ = nối 32 byte NHỊ PHÂN của từng hash (không nối chuỗi hex)",
            "text": "chuỗi (giờ, nơi nộp) băm dạng UTF-8 nguyên văn",
            "fileHashReadChunk": f"đọc file theo khúc {CHUNK_SIZE} byte; kết quả phải bằng băm cả file một lần",
        },
        "sha256_file": sha256_file_vectors(),
        "file_leaf": {
            "formula": "timeHash = SHA256(hashedAt); leafHash = SHA256(fileHash ‖ timeHash)",
            "cases": leaf_vectors(),
        },
        "bundle_per_file_time_v2": {
            "scheme": BUNDLE_SCHEME,
            "formula": "lá sắp theo (fileHash, leafHash) giảm dần; habc = SHA256(leaf_1 ‖ … ‖ leaf_n); "
                       "bundleHash = SHA256(habc ‖ SHA256(bundledAt))",
            "cases": bundle_vectors(),
        },
        "bundle_court_lot_v1": {
            "scheme": LOT_SCHEME,
            "formula": "habc như trên; lotMetaHash = SHA256(\"{place}|{fileCount}\"); "
                       "bundleHash = SHA256(habc ‖ SHA256(bundledAt) ‖ lotMetaHash)",
            "cases": lot_vectors(),
        },
        "merkle_bundle_legacy": {
            "formula": "nút trong = SHA256(0x01 ‖ trái ‖ phải); chia cây như RFC 6962 (tầng lẻ đẩy nút cuối lên, "
                       "không nhân đôi); 1 lá: gốc = lá, đường dẫn rỗng. Lá là bundleHash đưa thẳng vào, KHÔNG có "
                       "tiền tố 0x00: cách neo per_submission đang chạy. Cây theo bản ghi xem merkle_two_level.",
            "proofStep": "side = phía của hash anh em: L thì hash = SHA256(0x01 ‖ anh_em ‖ hiện_tại), R thì ngược lại",
            "cases": merkle_vectors(),
        },
        "receipt_signature_eip191": {
            "formula": "signedMessage (58 byte) = \"EVC-RECEIPT-v1\" (14) ‖ keyId u32 (4) ‖ seq u64 (8) ‖ recordHash (32), "
                       "big-endian; signature = EIP-191 personal_sign(signedMessage), hex 65 byte",
            "privateKey": TEST_SIGNING_KEY,
            "address": signer_address(TEST_SIGNING_KEY),
            "note": "Khóa test công khai (Hardhat #0), không dùng thật. Chữ ký EIP-191 tất định (RFC 6979) nên cố định.",
            "case": interim_receipt_signature_vector(),
        },
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUTPUT}")
