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
from app.core.merkle import build_tree
from app.core.signing import canonical_json, sign_receipt, signed_message, signer_address

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


def signature_vector() -> dict:
    receipt = {"receiptCode": "TX-0042", "type": "SELF", "submittedAt": "2026-11-04T21:05:35.16+07:00",
               "bundle": {"bundleHash": sha256_hex(b"bundle-demo")},
               "signer": {"algorithm": "EIP-191", "keyNo": 1, "address": signer_address(TEST_SIGNING_KEY)}}
    key_no, seq = 1, 42
    return {
        "note": "Khóa test công khai (Hardhat #0), không dùng thật. Chữ ký EIP-191 tất định (RFC 6979) nên cố định.",
        "privateKey": TEST_SIGNING_KEY,
        "address": signer_address(TEST_SIGNING_KEY),
        "keyNo": key_no,
        "seq": seq,
        "receipt": receipt,
        "canonicalJson": canonical_json(receipt).decode("utf-8"),
        "receiptDigest": sha256_hex(canonical_json(receipt)),
        "signedMessage": signed_message(key_no, seq, receipt).hex(),
        "signature": sign_receipt(TEST_SIGNING_KEY, key_no, seq, receipt),
    }


def build() -> dict:
    return {
        "version": "evidencechain-test-vectors-v1",
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
        "merkle": {
            "formula": "nút trong = SHA256(0x01 ‖ trái ‖ phải); tầng lẻ đẩy nút cuối lên (không nhân đôi); "
                       "1 lá: gốc = lá, đường dẫn rỗng. Lá đưa vào là bundleHash, CHƯA có tiền tố 0x00 "
                       "(RFC 6962 có): sẽ đổi khi chốt bản ghi 164 byte.",
            "proofStep": "side = phía của hash anh em: L thì hash = SHA256(0x01 ‖ anh_em ‖ hiện_tại), R thì ngược lại",
            "cases": merkle_vectors(),
        },
        "receipt_signature_eip191": {
            "formula": "signedMessage (58 byte) = \"EVCHAIN-RECEIPT1\" (16) ‖ keyNo (2, big-endian) ‖ seq (8, big-endian) "
                       "‖ SHA256(canonicalJson); signature = EIP-191 personal_sign(signedMessage), hex 65 byte",
            "case": signature_vector(),
        },
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUTPUT}")
