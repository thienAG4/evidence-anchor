"""Kiểm tra biên nhận (POST /verify, công khai): ai có file gốc + biên nhận đều tự kiểm được.

Biên nhận là JSON tải từ GET /receipts/{code}: {"receipt": {...}, "signature": "...", "anchor": {...} | null}.
"""
from collections import Counter
from typing import BinaryIO

from app.config import settings
from app.core import log_record as lr
from app.core.chain_reader import ChainReadError, get_anchor_tx
from app.core.hashing import BUNDLE_SCHEME, LOT_SCHEME, compute_bundle, compute_lot_bundle, hash_stream, leaf_hash
from app.core.merkle import verify_batch_proof
from app.core.payload import decode_anch
from app.core import receipt as receipt_signing
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError


def _recompute_bundle(receipt: dict) -> dict:
    files, bundled_at = receipt["files"], receipt["bundle"]["bundledAt"]
    if receipt["bundleScheme"] == BUNDLE_SCHEME:
        return compute_bundle(files, bundled_at)
    if receipt["bundleScheme"] == LOT_SCHEME:
        return compute_lot_bundle(files, bundled_at, receipt["place"], receipt["fileCount"])
    raise ValueError(f"Công thức {receipt['bundleScheme']} không hỗ trợ.")


def verify(document: dict, streams: list[BinaryIO]) -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str | None = None):
        checks.append({"name": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    try:
        receipt, signature = document["receipt"], document["signature"]
        receipt_files, bundle = receipt["files"], receipt["bundle"]
        anchor = document.get("anchor")
        expected = Counter(f["fileHash"] for f in receipt_files)
        recomputed = _recompute_bundle(receipt)
        leaves_ok = all(leaf_hash(f["fileHash"], f["hashedAt"]) == {"timeHash": f["timeHash"],
                                                                    "leafHash": f["leafHash"]}
                        for f in receipt_files)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise AppError(400, ErrorCode.INVALID_RECEIPT_FORMAT,
                       f"Biên nhận không đúng định dạng (cần file JSON tải từ GET /receipts/{{code}}): {exc}") from None

    signer = settings.receipt_signer_address or receipt_signing.signing_address()
    check("Chữ ký hệ thống trên biên nhận", receipt_signing.verify(receipt, signature, signer))

    actual = Counter(hash_stream(s) for s in streams)
    missing = [f["fileName"] for f in receipt_files if (expected - actual)[f["fileHash"]] > 0]
    extra = sum((actual - expected).values())
    detail = "; ".join(filter(None, [f"thiếu hoặc bị sửa: {', '.join(missing)}" if missing else None,
                                     f"{extra} file không thuộc biên nhận" if extra else None]))
    check("File tải lên khớp hash trong biên nhận", not missing and not extra, detail or None)
    check("Tính lại Hti, Ha từng file", leaves_ok)
    check("Tính lại Habc, Bundle", recomputed["habc"] == bundle["habc"]
          and recomputed["bundleHash"] == bundle["bundleHash"])

    if not anchor:
        check("Biên nhận đã được neo lên Sepolia", False,
              "chưa có phần anchor: tải lại biên nhận sau khi trạng thái là Đã neo")
    else:
        _check_records(check, receipt, anchor)

    return {"valid": all(c["ok"] for c in checks), "receiptCode": receipt.get("receiptCode"), "checks": checks}


def _check_records(check, receipt: dict, anchor: dict) -> None:
    """Mỗi file có 1 bản ghi 164 byte (A hoặc E) chứa đúng hash file; bản ghi đi qua cây hai tầng tới root đợt;
    payload của đợt chứa root đó và khoảng seq chứa bản ghi; payload là Input Data của giao dịch."""
    try:
        records = {r["fileCode"]: r for r in anchor["records"]}
        expected_event = lr.EVENT_A if receipt["type"] == "SELF" else lr.EVENT_E
        bad_records, bad_proofs, bad_payloads, payloads = [], [], [], {}
        for f in receipt["files"]:
            r = records.get(f["fileCode"])
            raw = bytes.fromhex(r["raw"]) if r else b""
            decoded = lr.decode(raw) if len(raw) == lr.RECORD_SIZE else None
            if not decoded or lr.record_hash(raw) != r["recordHash"] or decoded["fileHash"] != f["fileHash"] \
                    or decoded["eventType"] != expected_event or decoded["seq"] != r["seq"]:
                bad_records.append(f["fileCode"])
                continue
            if not verify_batch_proof(r["recordHash"], r["groupPath"], r["batchPath"], r["root"]):
                bad_proofs.append(f["fileCode"])
            try:
                batch = decode_anch(bytes.fromhex(r["payload"]))
            except ValueError:  # PayloadError: sai nhãn, phiên bản, độ dài
                batch = None
            if not batch or batch.root.hex() != r["root"] or batch.batch_no != r["batchNo"] \
                    or not r["fromSeq"] <= r["seq"] < r["fromSeq"] + batch.record_count:
                bad_payloads.append(f["fileCode"])
            payloads[r["txHash"]] = r["payload"]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise AppError(400, ErrorCode.INVALID_RECEIPT_FORMAT, f"Phần anchor của biên nhận không đúng định dạng: {exc}") \
            from None

    check(f"Bản ghi {lr.RECORD_SIZE} byte của từng file chứa đúng hash file", not bad_records,
          f"sai: {', '.join(bad_records)}" if bad_records else None)
    check("Đường dẫn Merkle từ từng bản ghi tới root đợt neo", not bad_proofs,
          f"sai: {', '.join(bad_proofs)}" if bad_proofs else None)
    check("Dữ liệu đợt neo chứa root và số thứ tự bản ghi", not bad_payloads,
          f"sai: {', '.join(bad_payloads)}" if bad_payloads else None)
    wallet = (settings.anchor_wallet_address or "").lower()
    for tx_hash, payload in payloads.items():  # các file thường cùng 1 giao dịch
        try:
            tx = get_anchor_tx(tx_hash)
        except ChainReadError as exc:
            raise AppError(502, ErrorCode.CHAIN_UNAVAILABLE, str(exc)) from None
        suffix = f" ({tx_hash[:10]}…)" if len(payloads) > 1 else ""
        check("Giao dịch neo tồn tại và thành công" + suffix, tx is not None and tx["success"])
        check("Input Data của giao dịch = dữ liệu đợt neo" + suffix, tx is not None and tx["input"] == payload.lower())
        if not wallet:
            check("Giao dịch gửi từ ví của hệ thống" + suffix, False, "server chưa cấu hình ANCHOR_WALLET_ADDRESS")
        else:
            check("Giao dịch gửi từ ví của hệ thống" + suffix, tx is not None and tx["from"] == wallet)
