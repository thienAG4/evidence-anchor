import json
import sys
from contextlib import ExitStack
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.hashing import hash_file
from app.services.legacy_receipt_service import create_receipt, verify_receipt

files = ["evidence_data/anhchup.jpg", "evidence_data/ghiam.m4a", "evidence_data/hopdong.docx"]

# Hash từng file (kèm thời gian, sleep 1-3s giữa các file) -> bundle -> đẩy lên Sepolia
with ExitStack() as stack:
    items = [(Path(f).name, stack.enter_context(open(f, "rb"))) for f in files]
    receipt = create_receipt(items)

for item in receipt["files"]:
    print(f"{item['fileName']}: {item['fileHash']} lúc {item['hashedAt']} -> {item['tx'].get('explorerUrl')}")
print("Bundle hash:", receipt["bundle"]["bundleHash"], "->", receipt["bundle"]["tx"]["explorerUrl"])

# Lưu biên lai cho người nộp
with open("receipt.json", "w", encoding="utf-8") as f:
    json.dump(receipt, f, indent=2, ensure_ascii=False)

result = verify_receipt(receipt, [hash_file(f) for f in files])
print("Khớp on-chain?", result["allOk"])
