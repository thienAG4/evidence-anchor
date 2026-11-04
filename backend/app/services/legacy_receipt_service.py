from collections import Counter
from typing import BinaryIO

from app.core.hashing import BUNDLE_SCHEME, compute_bundle, create_bundle, hash_evidence, now_vn
from app.db.history import append_history


def create_receipt(items: list[tuple[str, BinaryIO]]) -> dict:
    """Hash từng file (kèm thời gian) -> bundle -> đẩy bundle + hash từng file lên Sepolia."""
    from app.core.chain import account, anchor_to_sepolia

    submitted_at = now_vn()
    entries = hash_evidence(items)
    bundle = create_bundle(entries)
    bundle_tx = anchor_to_sepolia(bundle["bundleHash"])

    files = []
    for entry in entries:
        # Bundle đã lên chain: lỗi ở 1 file không được làm mất cả biên nhận.
        try:
            tx = anchor_to_sepolia(entry["fileHash"])
        except Exception as exc:
            tx = {"error": str(exc)}
        files.append({**entry, "tx": tx})

    receipt = {
        "bundleScheme": BUNDLE_SCHEME,
        "algorithm": "SHA-256",
        "network": "Sepolia",
        "anchoredBy": account.address,
        "submittedAt": submitted_at,
        "files": files,
        "bundle": {**bundle, "tx": bundle_tx},
    }
    append_history(receipt)
    return receipt


def verify_receipt(receipt: dict, actual_hashes: list[str]) -> dict:
    """Đối chiếu file tải lên + công thức bundle + giao dịch trên Sepolia."""
    from app.core.chain import account, verify_on_chain

    if receipt.get("bundleScheme") != BUNDLE_SCHEME:
        raise ValueError(f"Biên nhận không dùng công thức {BUNDLE_SCHEME}.")
    files = receipt["files"]
    bundle = receipt["bundle"]
    # Luôn kiểm theo ví của hệ thống, không tin "anchoredBy" trong biên nhận:
    # nếu không, ai cũng tự neo bằng ví riêng rồi ghi ví đó vào biên nhận giả là qua được.
    sender = account.address

    expected = Counter(f["fileHash"] for f in files)
    actual = Counter(actual_hashes)
    missing = [f["fileName"] for f in files if (expected - actual)[f["fileHash"]] > 0]
    extra_count = sum((actual - expected).values())

    recomputed = compute_bundle(files, bundle["bundledAt"])
    formula_ok = (recomputed["habc"] == bundle["habc"]
                  and recomputed["bundleHash"] == bundle["bundleHash"])

    bundle_on_chain = verify_on_chain(bundle["tx"]["txHash"], bundle["bundleHash"], sender)
    file_on_chain = [
        {"fileName": f["fileName"],
         "ok": "txHash" in f["tx"] and verify_on_chain(f["tx"]["txHash"], f["fileHash"], sender)}
        for f in files
    ]
    return {
        "filesMatch": not missing and extra_count == 0,
        "missing": missing,
        "extraCount": extra_count,
        "formulaOk": formula_ok,
        "bundleOnChain": bundle_on_chain,
        "fileOnChain": file_on_chain,
        "allOk": (not missing and extra_count == 0 and formula_ok and bundle_on_chain
                  and all(item["ok"] for item in file_on_chain)),
    }
