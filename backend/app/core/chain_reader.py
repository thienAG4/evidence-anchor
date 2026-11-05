"""Đọc giao dịch Sepolia bằng JSON-RPC thuần (requests), không nạp web3.

Server API chỉ cần đọc; nạp web3 trong tiến trình uvicorn làm --reload trên Windows treo.
Gửi giao dịch vẫn dùng core/chain.py (web3) trong worker neo.
"""
import requests

from app.config import settings


class ChainReadError(Exception):
    pass


def _rpc(method: str, params: list):
    try:
        response = requests.post(settings.sepolia_rpc_url, timeout=20,
                                 json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ChainReadError(f"Không gọi được RPC Sepolia: {exc}") from None
    if "error" in body:
        raise ChainReadError(f"RPC Sepolia báo lỗi: {body['error']}")
    return body.get("result")


def get_finalized_block_number() -> int:
    """Số block mới nhất mạng đã chốt (finalized): block cũ hơn không còn bị hủy, xếp lại."""
    block = _rpc("eth_getBlockByNumber", ["finalized", False])
    if not block:
        raise ChainReadError("RPC Sepolia không trả block finalized.")
    return int(block["number"], 16)


def get_anchor_tx(tx_hash: str) -> dict | None:
    """{from, to, input (không 0x), success, blockNumber}; None nếu không có giao dịch này."""
    tx = _rpc("eth_getTransactionByHash", [tx_hash])
    if tx is None:
        return None
    receipt = _rpc("eth_getTransactionReceipt", [tx_hash])
    return {
        "from": (tx.get("from") or "").lower(),
        "to": (tx.get("to") or "").lower(),
        "input": (tx.get("input") or "").removeprefix("0x").lower(),
        "success": receipt is not None and receipt.get("status") == "0x1",
        "blockNumber": int(tx["blockNumber"], 16) if tx.get("blockNumber") else None,
    }
