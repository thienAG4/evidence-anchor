"""Kiểm thử trọn quy trình F1 (lưu chứng) qua API thật, rồi tự kiểm tra biên nhận như đương sự sẽ làm.

Cần: server API đang chạy (localhost:8000), DB đã seed (tài khoản duongsu / 1234, thuky / 5678).
Muốn kiểm cả bước neo: điền PRIVATE_KEY trong .env và chạy worker neo ở terminal khác.

Chạy (từ gốc repo):
    venv\\Scripts\\python.exe backend/scripts/e2e_f1.py                      # tự tạo file mẫu
    venv\\Scripts\\python.exe backend/scripts/e2e_f1.py anh.jpg ghiam.m4a     # dùng file của bạn
    venv\\Scripts\\python.exe backend/scripts/e2e_f1.py --anchor-timeout 120  # chờ neo lâu hơn
"""
import argparse
import copy
import os
import sys
import tempfile
import time
from pathlib import Path

import requests

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core import log_record as lr
from app.core.hashing import compute_bundle, hash_file, leaf_hash
from app.core.payload import decode_anch
from app.core.merkle import verify_record_proof
from app.core.receipt import verify as verify_signature

results = []  # (trạng thái, tên bước)


def step(name: str, ok: bool | None, detail: str = "") -> bool:
    """ok=True: đạt, False: lỗi, None: bỏ qua."""
    mark = {True: "ĐẠT ", False: "LỖI ", None: "BỎ QUA"}[ok]
    results.append((ok, name))
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def section(title: str):
    print(f"\n== {title}")


class Api:
    def __init__(self, base: str):
        self.base = base

    def call(self, method: str, path: str, token: str | None = None, **kw) -> requests.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.request(method, self.base + path, headers=headers, timeout=120, **kw)

    def login(self, username: str, password: str) -> str:
        response = self.call("POST", "/auth/login", json={"username": username, "password": password})
        if response.status_code != 200:
            raise SystemExit(f"Không đăng nhập được {username}: {response.text} — đã chạy seed.py chưa?")
        return response.json()["token"]


def make_sample_files(folder: Path) -> list[Path]:
    """Đủ 4 loại được nhận: PDF, ảnh, video, âm thanh."""
    samples = {
        "hop-dong.pdf": b"%PDF-1.7\n" + os.urandom(80_000),
        "anh-hien-truong.jpg": b"\xff\xd8\xff\xe0" + os.urandom(150_000),
        "video-camera.mp4": b"\x00\x00\x00\x18ftypmp42" + os.urandom(300_000),
        "ghi-am-cuoc-goi.m4a": b"\x00\x00\x00\x20ftypM4A " + os.urandom(250_000),
    }
    paths = []
    for name, content in samples.items():
        path = folder / name
        path.write_bytes(content)
        paths.append(path)
    return paths


def verify_on_sepolia(anchor: dict) -> None:
    """Đọc giao dịch trên Sepolia (chỉ đọc, không cần ETH): Input Data phải là payload của đợt neo."""
    from dotenv import load_dotenv
    from web3 import Web3

    load_dotenv(BACKEND_DIR.parent / ".env")
    w3 = Web3(Web3.HTTPProvider(os.environ.get("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")))
    tx = w3.eth.get_transaction(anchor["txHash"])
    status = w3.eth.get_transaction_receipt(anchor["txHash"]).status
    on_chain = tx["input"].hex().removeprefix("0x")
    step("Giao dịch trên Sepolia thành công", status == 1, anchor["explorerUrl"])
    step("Input Data của giao dịch = payload đợt neo", on_chain == anchor["payload"], on_chain[:16] + "…")
    key = os.environ.get("PRIVATE_KEY")
    if key:
        wallet = w3.eth.account.from_key(key).address
        step("Giao dịch gửi từ ví của hệ thống", tx["from"].lower() == wallet.lower(), tx["from"])
    else:
        step("Giao dịch gửi từ ví của hệ thống", None, "không có PRIVATE_KEY để biết ví hệ thống")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="file cần lưu chứng (mặc định: tự tạo ảnh, ghi âm, PDF mẫu)")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--anchor-timeout", type=int, default=60, help="số giây chờ worker neo (0 = không chờ)")
    args = parser.parse_args()
    api = Api(args.base_url)
    tmp = Path(tempfile.mkdtemp(prefix="e2e-f1-"))
    files = [Path(f) for f in args.files] or make_sample_files(tmp)

    section("0. Chuẩn bị")
    try:
        api.call("GET", "/health")
    except requests.ConnectionError:
        raise SystemExit(f"Không kết nối được {args.base_url}: hãy chạy server API trước.")
    step("Server API đang chạy", True, args.base_url)
    step(f"{len(files)} file để lưu chứng", all(f.is_file() for f in files), ", ".join(f.name for f in files))

    section("1. Đăng nhập")
    party = api.login("duongsu", "1234")
    me = api.call("GET", "/me", party).json()
    step("Đương sự đăng nhập duongsu / 1234", me.get("role") == "PARTY", me.get("fullName", ""))
    clerk = api.login("thuky", "5678")
    step("Thư ký đăng nhập thuky / 5678", bool(clerk))
    r = api.call("POST", "/auth/login", json={"username": "duongsu", "password": "sai"})
    step("Sai mật khẩu bị từ chối", r.status_code == 401)

    section("2. Lưu chứng (F1)")
    with_handles = [(f, f.open("rb")) for f in files]
    try:
        r = api.call("POST", "/submissions", party,
                     files=[("files", (f.name, h, "application/octet-stream")) for f, h in with_handles])
    finally:
        for _, h in with_handles:
            h.close()
    body = r.json()
    step("Nộp file -> 202, nhận mã biên nhận", r.status_code == 202, body.get("receiptCode", r.text[:120]))
    if r.status_code != 202:
        return finish()
    code = body["receiptCode"]
    step("Mỗi file có mã riêng + giờ do server cấp", len(body["files"]) == len(files),
         ", ".join(f"{f['fileCode']} lúc {f['hashedAt'][11:22]}" for f in body["files"]))
    step("Trạng thái ban đầu: Chờ neo", body["status"] == "PENDING_ANCHOR", body["statusLabel"])
    r = api.call("POST", "/submissions", clerk, files=[("files", ("x.txt", b"x"))])
    step("Thư ký không lưu chứng được (chỉ đương sự)", r.status_code == 403)

    section("3. Tra cứu và quyền riêng tư (F1-AC4)")
    renamed = tmp / ("doi-ten" + files[0].suffix)
    renamed.write_bytes(files[0].read_bytes())
    with renamed.open("rb") as h:
        found = api.call("POST", "/submissions/lookup", party, files={"file": (renamed.name, h)}).json()
    # Cùng file đã lưu chứng từ trước (chạy lại với file của bạn) thì ra bản sớm nhất, không phải lần này
    step("Đưa lại file (đã đổi tên) -> tìm ra bản lưu chứng của mình", bool(found.get("fileCode")),
         f"{found.get('fileCode')} lúc {found.get('hashedAt')}")
    other = api.login("bidon", "1234")
    r = api.call("GET", f"/receipts/{code}", other)
    step("Đương sự khác không xem được biên nhận", r.status_code == 404)
    with files[0].open("rb") as h:
        r = api.call("POST", "/submissions/lookup", other, files={"file": (files[0].name, h)})
    step("Đương sự khác có cùng file cũng không tra cứu được", r.status_code == 404)

    section("4. Neo lên Sepolia (worker)")
    deadline = time.time() + args.anchor_timeout
    receipt_body = api.call("GET", f"/receipts/{code}", party).json()
    while receipt_body["status"] != "ANCHORED" and time.time() < deadline:
        time.sleep(5)
        receipt_body = api.call("GET", f"/receipts/{code}", party).json()
    status = receipt_body["status"]
    if status == "ANCHORED":
        step("Biên nhận chuyển sang Đã neo (block đã chốt)", True, receipt_body["anchor"]["explorerUrl"])
    elif status == "ANCHORED_UNFINALIZED":
        step("Biên nhận chuyển sang Đã neo", True, "block chưa chốt (~13 phút): biên nhận chưa hoàn chỉnh")
        step("Chưa chốt -> biên nhận chưa có phần anchor", receipt_body["anchor"] is None)
    elif status == "ANCHOR_FAILED":
        step("Biên nhận chuyển sang Đã neo", False, "neo lỗi — xem log worker (ví hết Sepolia ETH?)")
    else:
        step("Biên nhận chuyển sang Đã neo", None,
             f"vẫn Chờ neo sau {args.anchor_timeout}s — chưa chạy worker neo / chưa có PRIVATE_KEY")

    section("5. Đương sự tự kiểm tra biên nhận (không cần hỏi Tòa)")
    receipt, signature = receipt_body["receipt"], receipt_body["signature"]
    signer_address = api.call("GET", "/signing-key").json()["address"]
    step("Chữ ký hệ thống trên biên nhận hợp lệ (EIP-191)", verify_signature(receipt, signature, signer_address))
    step("Băm lại từng file gốc = fileHash trong biên nhận",
         [hash_file(str(f)) for f in files] == [f["fileHash"] for f in receipt["files"]])
    leaves_ok = all(leaf_hash(f["fileHash"], f["hashedAt"]) == {"timeHash": f["timeHash"], "leafHash": f["leafHash"]}
                    for f in receipt["files"])
    step("Tính lại Hti, Ha từng file khớp", leaves_ok)
    bundle = compute_bundle(receipt["files"], receipt["bundle"]["bundledAt"])
    step("Tính lại Habc, Bundle khớp", bundle["habc"] == receipt["bundle"]["habc"]
         and bundle["bundleHash"] == receipt["bundle"]["bundleHash"], bundle["bundleHash"][:16] + "…")
    anchor = receipt_body.get("anchor")
    if anchor:
        records = {r["fileCode"]: r for r in anchor["records"]}
        step("Mỗi file có bản ghi A 164 byte chứa đúng hash file", all(
            (r := records.get(f["fileCode"])) and len(raw := bytes.fromhex(r["raw"])) == lr.RECORD_SIZE
            and lr.record_hash(raw) == r["recordHash"] and lr.decode(raw)["fileHash"] == f["fileHash"]
            and lr.decode(raw)["eventType"] == lr.EVENT_A for f in receipt["files"]))
        step("Đường dẫn Merkle hai tầng từ từng bản ghi đi tới đúng root đợt neo",
             all(verify_record_proof(bytes.fromhex(r["recordHash"]), r["groupPath"], r["batchPath"], r["root"])
                 for r in records.values()))
        step("Dữ liệu đợt neo (payload) chứa root và seq của bản ghi", all(
            (p := decode_anch(bytes.fromhex(r["payload"]))).root.hex() == r["root"]
            and r["fromSeq"] <= r["seq"] < r["fromSeq"] + p.record_count
            for r in records.values()))
        try:
            for r in {r["txHash"]: r for r in records.values()}.values():  # các file thường cùng 1 giao dịch
                verify_on_sepolia(r)
        except Exception as exc:
            step("Đọc giao dịch trên Sepolia", False, repr(exc))
    else:
        step("Kiểm Merkle + giao dịch trên Sepolia", None, "biên nhận chưa được neo")

    section("6. Phát hiện chỉnh sửa")
    tampered_file = tmp / ("bi-sua" + files[0].suffix)
    data = bytearray(files[0].read_bytes())
    data[len(data) // 2] ^= 0x01  # đổi đúng 1 bit
    tampered_file.write_bytes(bytes(data))
    step("File bị sửa 1 bit -> hash khác biên nhận", hash_file(str(tampered_file)) != receipt["files"][0]["fileHash"])
    with tampered_file.open("rb") as h:
        r = api.call("POST", "/submissions/lookup", party, files={"file": (tampered_file.name, h)})
    step("File bị sửa -> tra cứu không ra", r.status_code == 404)
    forged = copy.deepcopy(receipt)
    forged["files"][0]["hashedAt"] = "2020-01-01T00:00:00.00+07:00"  # lùi ngày
    step("Sửa giờ trong biên nhận -> chữ ký không còn hợp lệ", not verify_signature(forged, signature, signer_address))
    forged_bundle = compute_bundle(forged["files"], forged["bundle"]["bundledAt"])
    step("Sửa giờ trong biên nhận -> Bundle tính lại khác", forged_bundle["bundleHash"] != receipt["bundle"]["bundleHash"])

    return finish()


def finish():
    passed = sum(1 for ok, _ in results if ok is True)
    failed = [name for ok, name in results if ok is False]
    skipped = [name for ok, name in results if ok is None]
    print(f"\n== Kết quả: {passed} đạt, {len(failed)} lỗi, {len(skipped)} bỏ qua")
    for name in failed:
        print(f"   LỖI: {name}")
    for name in skipped:
        print(f"   BỎ QUA: {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
