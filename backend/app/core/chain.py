"""Ví neo trên Sepolia, chỉ worker neo (app.workers.anchor_worker) dùng: nonce do AnchorState cấp, không chờ xác nhận.

Đọc giao dịch để kiểm tra biên nhận (POST /verify) ở app.core.chain_reader, không cần khóa ví.
"""
import os

from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import TransactionNotFound

load_dotenv()

w3 = Web3(Web3.HTTPProvider(os.environ["SEPOLIA_RPC_URL"]))
account = w3.eth.account.from_key(os.environ["PRIVATE_KEY"])
CHAIN_ID = 11155111  # Sepolia network
address = account.address


def pending_nonce() -> int:
    return w3.eth.get_transaction_count(account.address, "pending")


def sign(nonce: int, data: bytes, bump: int = 0) -> tuple[str, bytes]:
    """Ký giao dịch 0 ETH gửi cho chính mình, Input Data = data. bump > 0: gửi lại giao dịch kẹt, phí nhân 2^bump."""
    priority = w3.to_wei(2, "gwei") * 2 ** bump
    tx = {
        "chainId": CHAIN_ID,
        "to": account.address,
        "value": 0,
        "data": data,
        "nonce": nonce,
        "gas": 21000 + sum(16 if b else 4 for b in data),  # gas nội tại của giao dịch gửi tới ví (không có code)
        "maxPriorityFeePerGas": priority,
        "maxFeePerGas": w3.eth.get_block("latest")["baseFeePerGas"] * 2 * 2 ** bump + priority,
    }
    signed = account.sign_transaction(tx)
    tx_hash = signed.hash.hex()
    return (tx_hash if tx_hash.startswith("0x") else "0x" + tx_hash), signed.raw_transaction


def broadcast(raw: bytes) -> None:
    w3.eth.send_raw_transaction(raw)


def receipt(tx_hash: str) -> dict | None:
    """None khi giao dịch chưa lên khối."""
    try:
        r = w3.eth.get_transaction_receipt(tx_hash)
    except TransactionNotFound:
        return None
    return {"success": r.status == 1, "blockNumber": r.blockNumber,
            "blockTime": w3.eth.get_block(r.blockNumber).timestamp}


def finalized_block() -> int:
    return w3.eth.get_block("finalized").number
