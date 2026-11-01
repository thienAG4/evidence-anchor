import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from web3 import Web3

from hashutils import vietnam_tz

load_dotenv()

w3 = Web3(Web3.HTTPProvider(os.environ["SEPOLIA_RPC_URL"]))
account = w3.eth.account.from_key(os.environ["PRIVATE_KEY"])
CHAIN_ID = 11155111  # Sepolia network


def anchor_to_sepolia(hash_value: str) -> dict:
    """Ghi một hash SHA-256 lên Sepolia (tx 0 ETH gửi cho chính mình), trả về link + thông tin truy vấn."""
    latest = w3.eth.get_block("latest")
    priority = w3.to_wei(2, "gwei")

    tx = {
        "chainId": CHAIN_ID,
        "to": account.address,
        "value": 0,
        "data": "0x" + hash_value,
        "nonce": w3.eth.get_transaction_count(account.address, "pending"),
        "maxPriorityFeePerGas": priority,
        "maxFeePerGas": latest["baseFeePerGas"] * 2 + priority,
    }
    tx["gas"] = w3.eth.estimate_gas(tx)

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError(f"Giao dịch thất bại: {tx_hash.hex()}")
    block = w3.eth.get_block(receipt.blockNumber)

    tx_hash_hex = tx_hash.hex()
    if not tx_hash_hex.startswith("0x"):
        tx_hash_hex = "0x" + tx_hash_hex

    return {
        "txHash": tx_hash_hex,
        "explorerUrl": f"https://sepolia.etherscan.io/tx/{tx_hash_hex}",
        "blockNumber": receipt.blockNumber,
        "blockTimestampUnix": block.timestamp,
        "blockTimeISO": datetime.fromtimestamp(block.timestamp, tz=timezone.utc).isoformat(),
        "blockTimeVN": datetime.fromtimestamp(block.timestamp, tz=vietnam_tz).strftime("%d/%m/%Y %H:%M:%S"),
    }


def verify_on_chain(tx_hash: str, expected_hash: str, expected_sender: str = None) -> bool:
    """Giao dịch thành công, đúng ví gửi, và Input Data trùng hash cần kiểm tra."""
    tx = w3.eth.get_transaction(tx_hash)
    if w3.eth.get_transaction_receipt(tx_hash).status != 1:
        return False
    if expected_sender and tx["from"].lower() != expected_sender.lower():
        return False
    on_chain = tx["input"].hex().removeprefix("0x")
    return on_chain == expected_hash
