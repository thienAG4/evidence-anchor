import json
from pathlib import Path

HISTORY_PATH = Path(__file__).resolve().parent / "history.json"


def load_history() -> list[dict]:
    """Đọc lịch sử biên nhận đã tạo (rỗng nếu chưa có)."""
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def append_history(receipt: dict) -> None:
    """Ghi tóm tắt 1 biên nhận vào history.json."""
    history = load_history()
    history.append({
        "submittedAt": receipt["submittedAt"],
        "fileCount": len(receipt["files"]),
        "files": [f["fileName"] for f in receipt["files"]],
        "bundleHash": receipt["bundle"]["bundleHash"],
        "explorerUrl": receipt["bundle"]["tx"].get("explorerUrl"),
    })
    HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
