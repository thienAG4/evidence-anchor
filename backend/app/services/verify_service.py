"""Kiểm tra biên nhận (POST /verify, công khai): ai có file gốc + biên nhận đều tự kiểm được.

Biên nhận là JSON tải từ GET /receipts/{code}: {"receipt": {...}, "signature": "...", "anchor": {...} | null}.
"""
from collections import Counter
from typing import BinaryIO

from app.config import settings
from app.core.chain_reader import ChainReadError, get_anchor_tx
from app.core.hashing import BUNDLE_SCHEME, LOT_SCHEME, compute_bundle, compute_lot_bundle, hash_stream, leaf_hash
from app.core.merkle import verify_proof
from app.core.receipt import signing_public_key
from app.core.signing import verify_signature
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

    check("Chữ ký hệ thống trên biên nhận", verify_signature(signing_public_key(), receipt, signature))

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
        check("Đường dẫn Merkle từ Bundle tới gốc đã neo",
              verify_proof(bundle["bundleHash"], anchor["merkleProof"], anchor["rootHash"]))
        try:
            tx = get_anchor_tx(anchor["txHash"])
        except ChainReadError as exc:
            raise AppError(502, ErrorCode.CHAIN_UNAVAILABLE, str(exc)) from None
        check("Giao dịch neo tồn tại và thành công", tx is not None and tx["success"])
        check("Input Data của giao dịch = gốc đã neo", tx is not None and tx["input"] == anchor["rootHash"])
        wallet = (settings.anchor_wallet_address or "").lower()
        if not wallet:
            check("Giao dịch gửi từ ví của hệ thống", False, "server chưa cấu hình ANCHOR_WALLET_ADDRESS")
        else:
            check("Giao dịch gửi từ ví của hệ thống", tx is not None and tx["from"] == wallet)

    return {"valid": all(c["ok"] for c in checks), "receiptCode": receipt.get("receiptCode"), "checks": checks}
