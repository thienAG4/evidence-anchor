"""Kiểm thử trọn quy trình tại Tòa: lưu chứng -> nộp lô -> so hash -> xem kết quả -> giám định -> chốt hồ sơ
-> phúc thẩm đối chiếu -> kiểm biên nhận -> nhật ký truy cập. Mỗi lần chạy tạo 1 vụ án mới.

Cần: server API đang chạy (localhost:8000), DB đã seed (backend/scripts/seed.py).
Chạy (từ gốc repo): venv\\Scripts\\python.exe backend/scripts/e2e_court.py
"""
import io
import json
import os
import re
import sys
import time

import requests

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
HASH_RE = re.compile(r"\b[0-9a-f]{64}\b")
results = []


def step(name: str, ok: bool, detail: str = "") -> bool:
    results.append((ok, name))
    print(f"  [{'ĐẠT' if ok else 'LỖI'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def section(title: str):
    print(f"\n== {title}")


def call(method: str, path: str, token: str | None = None, **kw) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.request(method, BASE + path, headers=headers, timeout=120, **kw)


def expect(name: str, response: requests.Response, status: int, code: str | None = None) -> dict:
    body = response.json() if response.content else {}
    ok = response.status_code == status and (code is None or body.get("error", {}).get("code") == code)
    got = f"{response.status_code} {body.get('error', {}).get('code', '')}".strip()
    step(name, ok, got if not ok or code else "")
    return body


def label(body: dict) -> str:
    return body.get("label") or body.get("result", {}).get("label", "")


def login(username: str, password: str) -> str:
    response = call("POST", "/auth/login", json={"username": username, "password": password})
    if response.status_code != 200:
        raise SystemExit(f"Không đăng nhập được {username}: {response.text} — đã chạy seed.py chưa?")
    return response.json()["token"]


def upload(name: str, content: bytes, key: str = "files"):
    return (key, (name, io.BytesIO(content), "application/octet-stream"))


def no_hash(name: str, body) -> bool:
    found = HASH_RE.findall(json.dumps(body))
    return step(name, not found, f"lộ {len(found)} mã hash" if found else "")


def main():
    try:
        call("GET", "/health")
    except requests.ConnectionError:
        raise SystemExit(f"Không kết nối được {BASE}: hãy chạy server API trước.")

    # Nội dung file giả lập: hợp đồng, ảnh, ghi âm
    contract = b"%PDF-1.7\nHop dong mua ban 500 tan gao\n" + os.urandom(40_000)
    photo = b"\xff\xd8\xff\xe0" + os.urandom(60_000)
    photo_edited = photo[:-1] + bytes([photo[-1] ^ 0xFF])  # ảnh bị sửa 1 byte (hoặc nén lại)
    recording = b"\x00\x00\x00\x20ftypM4A " + os.urandom(80_000)

    section("1. Đăng nhập các vai")
    plaintiff = login("duongsu", "1234")
    clerk = login("thuky", "5678")
    defendant = login("bidon", "1234")
    outsider = login("luatsu", "1234")  # không được thêm vào vụ mới -> người ngoài vụ
    judge = login("thamphan", "5678")
    appeal_clerk = login("thuky.phuctham", "5678")
    admin = login("admin", "5678")
    step("Đương sự duongsu/1234, thư ký thuky/5678 và các vai khác đều đăng nhập được",
         all([clerk, appeal_clerk, judge, admin, plaintiff, defendant, outsider]))
    expect("Sai mật khẩu -> INVALID_CREDENTIALS", call("POST", "/auth/login", json={
        "username": "duongsu", "password": "sai"}), 401, "INVALID_CREDENTIALS")
    me = call("GET", "/me", plaintiff).json()
    step("duongsu là đương sự (PARTY)", me.get("role") == "PARTY", me.get("fullName", ""))

    section("2. Vụ án và người tham gia")
    case_number = f"E2E-{int(time.time())}/2026/DS-ST"
    case = expect("Thư ký tạo vụ án", call("POST", "/cases", clerk, json={
        "caseNumber": case_number, "title": "Tranh chấp hợp đồng mua bán gạo"}), 201)
    case_id = case["id"]
    step("Thư ký tạo vụ tự là thư ký của vụ", case.get("myRoles") == ["CLERK"], case.get("courtName", ""))
    expect("Tạo trùng số vụ -> CASE_EXISTS", call("POST", "/cases", clerk, json={
        "caseNumber": case_number, "title": "x"}), 409, "CASE_EXISTS")
    expect("Đương sự không tạo được vụ", call("POST", "/cases", plaintiff, json={
        "caseNumber": "X", "title": "x"}), 403, "FORBIDDEN")
    ids = {}
    for username in ("duongsu", "bidon", "thamphan", "thuky.phuctham"):
        ids[username] = call("GET", f"/users/lookup?username={username}", clerk).json()["id"]
    for who, role in (("duongsu", "PLAINTIFF"), ("bidon", "DEFENDANT"), ("thamphan", "JUDGE")):
        expect(f"Thêm {who} vào vụ với vai trò {role}", call("POST", f"/cases/{case_id}/participants", clerk,
                                                             json={"userId": ids[who], "roleInCase": role}), 201)
    expect("Đương sự không làm thẩm phán được -> INVALID_PARTICIPANT_ROLE", call(
        "POST", f"/cases/{case_id}/participants", clerk, json={"userId": ids["bidon"], "roleInCase": "JUDGE"}),
        400, "INVALID_PARTICIPANT_ROLE")
    expect("Thêm trùng -> PARTICIPANT_EXISTS", call("POST", f"/cases/{case_id}/participants", clerk, json={
        "userId": ids["bidon"], "roleInCase": "DEFENDANT"}), 409, "PARTICIPANT_EXISTS")
    mine = call("GET", "/cases", plaintiff).json()["items"]
    step("Nguyên đơn thấy vụ trong danh sách của mình", any(c["id"] == case_id for c in mine))
    expect("Người ngoài vụ không xem được vụ", call("GET", f"/cases/{case_id}", outsider), 403,
           "NOT_CASE_PARTICIPANT")
    step("Người ngoài vụ không thấy vụ trong danh sách",
         all(c["id"] != case_id for c in call("GET", "/cases", outsider).json()["items"]))

    section("3. F1 — Nguyên đơn lưu chứng trước khi kiện")
    r = expect("Nhận đủ 4 loại: PDF, ảnh, video, âm thanh", call("POST", "/submissions", plaintiff, files=[
        upload("bien-ban.pdf", b"%PDF-1.4\n" + os.urandom(3000)), upload("anh.png", b"\x89PNG\r\n\x1a\n" + os.urandom(3000)),
        upload("clip.mp4", b"\x00\x00\x00\x18ftypmp42" + os.urandom(3000)),
        upload("ghi-am.mp3", b"ID3\x04\x00" + os.urandom(3000))]), 202)
    step("4 file được nhận, mỗi file 1 mã", len(r.get("files", [])) == 4)
    for name, content in (("caidat.exe", b"MZ\x90\x00" + os.urandom(500)), ("tailieu.zip", b"PK\x03\x04" + os.urandom(500)),
                          ("ghichu.txt", b"ghi chu"), ("hopdong.docx", b"PK\x03\x04" + os.urandom(500))):
        r = expect(f"Từ chối {name}", call("POST", "/submissions", plaintiff, files=[upload(name, content)]),
                   400, "FILE_TYPE_NOT_ALLOWED")
    step("Thông báo nói rõ chỉ nhận loại nào", "PDF, ảnh" in r["error"]["message"], r["error"]["message"])
    r = expect("Từ chối file .exe đổi tên thành .jpg", call("POST", "/submissions", plaintiff, files=[
        upload("anh-gia.jpg", b"MZ\x90\x00" + os.urandom(500))]), 400, "FILE_TYPE_NOT_ALLOWED")
    step("Thông báo nói rõ nội dung không khớp đuôi", "nội dung không phải" in r["error"]["message"],
         r["error"]["message"])
    expect("1 file lạ trong lô -> cả lần nộp bị từ chối, không lưu gì", call("POST", "/submissions", plaintiff, files=[
        upload("ok.pdf", contract), upload("x.exe", b"MZ" + os.urandom(100))]), 400, "FILE_TYPE_NOT_ALLOWED")
    sub = expect("Lưu chứng hợp đồng + ảnh", call("POST", "/submissions", plaintiff, files=[
        upload("hop-dong.pdf", contract), upload("anh-giao-hang.jpg", photo)]), 202)
    code_contract, code_photo = sub["files"][0]["fileCode"], sub["files"][1]["fileCode"]
    step("Mỗi file có mã biên nhận để ghi vào danh mục kèm đơn", bool(code_contract and code_photo),
         f"{code_contract}, {code_photo}")

    section("4. F7 — Thư ký tra mã biên nhận")
    base = expect("Tra mã -> giờ lưu chứng + người lưu", call("GET", f"/baselines/{code_contract}", clerk), 200)
    step("Thấy người lưu, giờ lưu", base.get("ownerName") == "Nguyễn Văn An" and bool(base.get("hashedAt")),
         f"{base.get('ownerName')} lúc {base.get('hashedAt')}")
    no_hash("Không lộ hash, không có file", base)
    expect("Mã không tồn tại -> FILE_CODE_NOT_FOUND", call("GET", "/baselines/TX-9999-9", clerk), 404,
           "FILE_CODE_NOT_FOUND")
    expect("Đương sự không tra mã của người khác", call("GET", f"/baselines/{code_contract}", defendant), 403)

    section("5. F2 + F3 — Nộp chứng cứ tại Tòa, hệ thống tự so")
    lot_files = [upload("hop-dong.pdf", contract), upload("anh-giao-hang.jpg", photo_edited),
                 upload("ghi-am.m4a", recording)]
    meta = json.dumps([{"fileCode": code_contract}, {"fileCode": code_photo}, {"fileCode": ""}])
    expect("meta khác số file -> META_MISMATCH", call("POST", f"/cases/{case_id}/lots", clerk, files=lot_files,
                                                      data={"meta": json.dumps([{"fileCode": ""}])}), 400,
           "META_MISMATCH")
    lot_files = [upload("hop-dong.pdf", contract), upload("anh-giao-hang.jpg", photo_edited),
                 upload("ghi-am.m4a", recording)]
    expect("Mã sai -> báo lỗi, không lưu, không so", call("POST", f"/cases/{case_id}/lots", clerk, files=lot_files,
                                                         data={"meta": json.dumps([{"fileCode": "TX-9999-1"},
                                                                                   {"fileCode": ""},
                                                                                   {"fileCode": ""}])}),
           404, "FILE_CODE_NOT_FOUND")
    step("Sau lỗi mã sai: vụ chưa có lô nào", call("GET", f"/cases/{case_id}/lots", clerk).json()["items"] == [])
    expect("Đương sự không nộp lô qua app được (F2-AC4)", call("POST", f"/cases/{case_id}/lots", plaintiff,
                                                               files=[upload("a.pdf", contract)]), 403)
    lot_files = [upload("hop-dong.pdf", contract), upload("anh-giao-hang.jpg", photo_edited),
                 upload("ghi-am.m4a", recording)]
    lot = expect("Thư ký nạp lô 3 file", call("POST", f"/cases/{case_id}/lots", clerk, files=lot_files,
                                              data={"meta": meta}), 202)
    lot_id = lot["lotId"]
    labels = [f["result"]["label"] for f in lot["files"]]
    step("Hợp đồng giống bản lưu chứng -> KHỚP BẢN LƯU CHỨNG", labels[0] == "KHỚP BẢN LƯU CHỨNG", labels[0])
    step("Ảnh đã bị sửa -> KHÁC BẢN LƯU CHỨNG", labels[1] == "KHÁC BẢN LƯU CHỨNG", labels[1])
    step("Ghi âm chưa từng lưu chứng -> KHÔNG CÓ MỐC ĐỂ SO", labels[2] == "KHÔNG CÓ MỐC ĐỂ SO", labels[2])
    step("Lô số 1, có ngày giờ + nơi nộp do hệ thống ghi", lot["lotNo"] == 1 and bool(lot["place"]),
         f"lô {lot['lotNo']}, {lot['place']}, {lot['receivedAt']}")
    no_hash("Kết quả nộp lô không lộ hash", lot)
    evidence = {f["fileName"]: f["evidenceId"] for f in lot["files"]}

    section("6. F5 — Xem kết quả (phiên họp, xét xử)")
    for who, token in (("Thẩm phán", judge), ("Nguyên đơn", plaintiff), ("Bị đơn", defendant)):
        view = expect(f"{who} xem kết quả các lô", call("GET", f"/cases/{case_id}/lots", token), 200)
        item = view["items"][0]
        step(f"{who}: có kết quả cả lô + từng chứng cứ + 'Kiểm tra lúc' + chú thích cố định",
             label(item) == "KHỚP BẢN ĐÃ GHI" and all(f["result"]["checkedAt"] for f in item["files"])
             and item["disclaimer"] == "Chỉ so với bản đã lưu, không xác định thật giả.", label(item))
        no_hash(f"{who}: không màn hình nào hiện mã hash", view)
    step("Đương sự không thấy thông tin bản lưu chứng của người khác",
         all("baseline" not in f for f in call("GET", f"/cases/{case_id}/lots", defendant).json()["items"][0]["files"]))
    expect("Người ngoài vụ không xem được kết quả", call("GET", f"/cases/{case_id}/lots", outsider), 403)

    section("7. F3-AC5 — Về sau tính lại hash tổng của lô")
    # Hàm, không phải list: mỗi lần gửi cần luồng file mới (luồng đã đọc hết thì gửi đi là file rỗng)
    same = lambda: [upload("1.pdf", contract), upload("3.m4a", recording), upload("2.jpg", photo_edited)]
    r = expect("Chọn lại đủ 3 file (đổi tên, đổi thứ tự)", call(
        "POST", f"/cases/{case_id}/lots/{lot_id}/checks", clerk, files=same()), 200)
    step("-> KHỚP BẢN ĐÃ GHI", label(r) == "KHỚP BẢN ĐÃ GHI", label(r))
    for name, files in (("Bớt 1 file", [upload("1.pdf", contract), upload("2.jpg", photo_edited)]),
                        ("Thêm 1 file lạ", [upload("1.pdf", contract), upload("2.jpg", photo_edited),
                                            upload("3.m4a", recording), upload("4.jpg", b"\xff\xd8\xff\xe0them")]),
                        ("Đổi ảnh về bản gốc", [upload("1.pdf", contract), upload("2.jpg", photo),
                                                upload("3.m4a", recording)])):
        r = call("POST", f"/cases/{case_id}/lots/{lot_id}/checks", clerk, files=files).json()
        step(f"{name} -> KHÁC BẢN ĐÃ GHI", label(r) == "KHÁC BẢN ĐÃ GHI", label(r))
    view = call("GET", f"/cases/{case_id}/lots/{lot_id}", judge).json()
    step("Màn hình kết quả hiện lần tính lại gần nhất kèm giờ", label(view) == "KHÁC BẢN ĐÃ GHI",
         f"{label(view)} lúc {view['result']['checkedAt']}")
    r = call("POST", f"/cases/{case_id}/evidence/{evidence['ghi-am.m4a']}/checks", clerk,
             files=[upload("x.m4a", recording, "file")]).json()
    step("Kiểm lại 1 chứng cứ: ghi âm còn nguyên -> KHỚP BẢN ĐÃ GHI", label(r) == "KHỚP BẢN ĐÃ GHI", label(r))

    section("8. F3-AC6 — Nộp bổ sung")
    lot2 = expect("Nộp bổ sung 1 file", call("POST", f"/cases/{case_id}/lots", clerk,
                                             files=[upload("bien-ban.pdf", b"%PDF-1.4\n" + os.urandom(9000))]), 202)
    step("Lô mới đánh số 2", lot2["lotNo"] == 2, f"lô {lot2['lotNo']}")
    r = call("POST", f"/cases/{case_id}/lots/{lot_id}/checks", clerk, files=same()).json()
    step("Lô 1 không bị sửa: tính lại vẫn KHỚP BẢN ĐÃ GHI", label(r) == "KHỚP BẢN ĐÃ GHI", label(r))

    section("9. F4 — Giám định ảnh (thư ký ghi thay)")
    steps_url = f"/cases/{case_id}/evidence/{evidence['anh-giao-hang.jpg']}/appraisal-steps"
    expect("Nhận về khi chưa gửi -> INVALID_STATE", call("POST", steps_url, clerk, data={"step": "RETURN"},
                                                         files=[upload("a.jpg", photo_edited, "file")]), 409,
           "INVALID_STATE")
    expect("Gửi đi file khác bản đã ghi lúc nhận -> FILE_CHANGED_SINCE_RECEIPT", call(
        "POST", steps_url, clerk, data={"step": "SEND"}, files=[upload("a.jpg", photo, "file")]), 409,
        "FILE_CHANGED_SINCE_RECEIPT")
    r = expect("Gửi đi đúng bản đã ghi lúc nhận (dù KHÁC BẢN LƯU CHỨNG vẫn được giám định)", call(
        "POST", steps_url, clerk, data={"step": "SEND"}, files=[upload("a.jpg", photo_edited, "file")]), 201)
    step("Bước gửi đi: KHỚP BẢN ĐÃ GHI", label(r) == "KHỚP BẢN ĐÃ GHI", label(r))
    expect("Gửi lại khi chưa nhận về -> INVALID_STATE", call("POST", steps_url, clerk, data={"step": "SEND"},
                                                             files=[upload("a.jpg", photo_edited, "file")]), 409,
           "INVALID_STATE")
    r = expect("Nhận về file đã bị đổi vẫn ghi được", call("POST", steps_url, clerk, data={"step": "RETURN"},
                                                           files=[upload("a.jpg", b"\xff\xd8\xff\xe0anh da sua", "file")]), 201)
    step("Bước nhận về: KHÁC BẢN ĐÃ GHI (biết khác ở bước nào)", label(r) == "KHÁC BẢN ĐÃ GHI", label(r))
    history = expect("Thẩm phán xem các bước giám định", call("GET", steps_url, judge), 200)
    step("Có 2 bước: gửi đi khớp, nhận về khác",
         [(s["step"], s["result"]["value"]) for s in history["items"]] == [("SEND", "UNCHANGED"),
                                                                          ("RETURN", "CHANGED")])
    no_hash("Lịch sử giám định không lộ hash", history)

    section("10. F9 — Kháng cáo, chốt hồ sơ, phúc thẩm đối chiếu")
    docs = ["Hợp đồng mua bán", "Ảnh giao hàng", "Ghi âm cuộc gọi"]
    dossier_files = lambda: [upload("hd.pdf", contract), upload("anh.jpg", photo_edited), upload("ga.m4a", recording)]
    expect("Chốt hồ sơ khi chưa kháng cáo -> APPEAL_REQUIRED", call(
        "POST", f"/cases/{case_id}/dossiers", clerk, files=dossier_files(), data={"docNames": docs}), 409,
        "APPEAL_REQUIRED")
    expect("Chuyển APPEAL mà thiếu loại kháng cáo -> INVALID_STATE", call(
        "PATCH", f"/cases/{case_id}", clerk, json={"status": "APPEAL"}), 409, "INVALID_STATE")
    r = expect("Ghi nhận kháng cáo", call("PATCH", f"/cases/{case_id}", clerk,
                                          json={"status": "APPEAL", "appealType": "KHANG_CAO"}), 200)
    step("Vụ chuyển APPEAL / KHANG_CAO", (r.get("status"), r.get("appealType")) == ("APPEAL", "KHANG_CAO"))
    expect("Tên tài liệu khác số file -> META_MISMATCH", call(
        "POST", f"/cases/{case_id}/dossiers", clerk, files=dossier_files(), data={"docNames": docs[:2]}), 400,
        "META_MISMATCH")
    dossier = expect("Chốt hồ sơ 3 tài liệu", call("POST", f"/cases/{case_id}/dossiers", clerk,
                                                   files=dossier_files(), data={"docNames": docs}), 201)
    step("Bản ghi chốt có giờ + người chốt", bool(dossier.get("recordedAt")) and dossier.get("createdBy") == "Lê Thị Thư Ký")
    check_url = f"/dossiers/{dossier['dossierId']}/checks"
    expect("Thư ký phúc thẩm chưa được thêm vào vụ -> không đối chiếu được", call(
        "POST", check_url, appeal_clerk, files=dossier_files(), data={"docNames": docs}), 403)
    expect("Thêm thư ký Tòa phúc thẩm vào vụ", call("POST", f"/cases/{case_id}/participants", clerk, json={
        "userId": ids["thuky.phuctham"], "roleInCase": "CLERK"}), 201)
    r = call("POST", check_url, appeal_clerk, files=dossier_files(), data={"docNames": docs}).json()
    step("Phúc thẩm nhận nguyên vẹn -> KHỚP BẢN ĐÃ GHI", label(r) == "KHỚP BẢN ĐÃ GHI", label(r))
    r = call("POST", check_url, appeal_clerk, files=dossier_files(),
             data={"docNames": ["Hợp đồng", "Ảnh giao hàng", "Ghi âm cuộc gọi"]}).json()
    step("Đổi tên trong danh mục -> KHÁC BẢN ĐÃ GHI", label(r) == "KHÁC BẢN ĐÃ GHI", label(r))
    r = call("POST", check_url, appeal_clerk, data={"docNames": docs},
             files=[upload("hd.pdf", contract), upload("anh.jpg", photo), upload("ga.m4a", recording)]).json()
    step("Đổi 1 file -> KHÁC BẢN ĐÃ GHI", label(r) == "KHÁC BẢN ĐÃ GHI", label(r))
    expect("Thẩm phán xem hồ sơ chốt", call("GET", f"/cases/{case_id}/dossiers", judge), 200)
    expect("Đương sự không xem hồ sơ chốt", call("GET", f"/cases/{case_id}/dossiers", plaintiff), 403)

    section("11. Kiểm tra biên nhận công khai (POST /verify)")
    document = call("GET", f"/receipts/{sub['receiptCode']}", plaintiff).json()
    receipt_file = lambda doc: ("receipt", ("receipt.json", io.BytesIO(json.dumps(doc).encode()), "application/json"))
    r = expect("Gửi biên nhận + file gốc (không cần đăng nhập)", call(
        "POST", "/verify", files=[receipt_file(document), upload("a.pdf", contract), upload("b.jpg", photo)]), 200)
    checks = {c["name"]: c["ok"] for c in r["checks"]}
    step("Chữ ký, file, Ha, Habc, Bundle đều khớp",
         all(checks[n] for n in ("Chữ ký hệ thống trên biên nhận", "File tải lên khớp hash trong biên nhận",
                                 "Tính lại Hti, Ha từng file", "Tính lại Habc, Bundle")))
    step("Chưa neo -> valid = false, báo rõ chưa neo",
         r["valid"] is False and checks.get("Biên nhận đã được neo lên Sepolia") is False)
    r = call("POST", "/verify", files=[receipt_file(document), upload("a.pdf", contract),
                                       upload("b.jpg", photo_edited)]).json()
    step("File bị sửa -> báo file không khớp",
         not {c["name"]: c["ok"] for c in r["checks"]}["File tải lên khớp hash trong biên nhận"])
    forged = json.loads(json.dumps(document))
    forged["receipt"]["submittedAt"] = "2020-01-01T00:00:00.00+07:00"
    r = call("POST", "/verify", files=[receipt_file(forged), upload("a.pdf", contract), upload("b.jpg", photo)]).json()
    step("Biên nhận bị sửa ngày -> chữ ký không hợp lệ",
         not {c["name"]: c["ok"] for c in r["checks"]}["Chữ ký hệ thống trên biên nhận"])
    expect("Biên nhận sai định dạng -> INVALID_RECEIPT_FORMAT", call(
        "POST", "/verify", files=[receipt_file({"x": 1}), upload("a.pdf", contract)]), 400, "INVALID_RECEIPT_FORMAT")

    section("11b. Giao diện thư ký (/clerk) — đối chiếu biên nhận lưu chứng")
    view = expect("Thư ký xem các lần lưu chứng của đương sự trong vụ mình", call("GET", "/clerk/receipts", clerk), 200)
    mine = [r for r in view["items"] if r["receiptCode"] == sub["receiptCode"]]
    step("Có biên nhận của nguyên đơn, kèm tên người lưu", bool(mine) and mine[0]["owner"]["fullName"] == "Nguyễn Văn An")
    no_hash("Danh sách cho thư ký không lộ mã hash", view)
    expect("Đương sự không vào được API thư ký", call("GET", "/clerk/receipts", plaintiff), 403)
    people = call("GET", "/clerk/litigants", clerk).json()["items"]
    step("Trang Đương sự có duongsu", any(p["username"] == "duongsu" for p in people))
    if mine and mine[0]["status"] != "ANCHORED":
        expect("Chưa neo (chưa khóa) -> chưa đối chiếu được", call(
            "POST", f"/clerk/receipts/{sub['receiptCode']}/compare", clerk, data={"fileCode": code_contract},
            files=[upload("hd.pdf", contract, "file")]), 409, "INVALID_STATE")

    section("12. Đóng vụ")
    expect("Đóng vụ", call("PATCH", f"/cases/{case_id}", clerk, json={"status": "CLOSED"}), 200)
    expect("Vụ đã đóng -> không nhận lô mới (CASE_CLOSED)", call(
        "POST", f"/cases/{case_id}/lots", clerk, files=[upload("a.pdf", contract)]), 409, "CASE_CLOSED")
    expect("Vụ đã đóng -> không mở lại được", call("PATCH", f"/cases/{case_id}", clerk, json={"status": "OPEN"}),
           409, "INVALID_STATE")

    section("13. F8 — Quản trị và nhật ký truy cập")
    expect("Đương sự không vào được trang quản trị", call("GET", "/admin/users", plaintiff), 403)
    new_user = f"thuky.moi{int(time.time())}"
    created = expect("Admin tạo tài khoản thư ký mới", call("POST", "/admin/users", admin, json={
        "username": new_user, "email": f"{new_user}@evidencechain.test", "fullName": "Thư Ký Mới",
        "role": "CLERK", "courtName": "TAND Quận 3"}), 201)
    temp = created.get("temporaryPassword")
    step("Có mật khẩu tạm và đăng nhập được", bool(temp) and call(
        "POST", "/auth/login", json={"username": new_user, "password": temp}).status_code == 200)
    expect("Trùng tên đăng nhập -> USERNAME_EXISTS", call("POST", "/admin/users", admin, json={
        "username": "duongsu", "email": "khac@evidencechain.test", "fullName": "X", "role": "PARTY"}),
        409, "USERNAME_EXISTS")
    expect("Admin khóa tài khoản", call("PATCH", f"/admin/users/{created['id']}", admin,
                                        json={"status": "DISABLED"}), 200)
    expect("Tài khoản bị khóa không đăng nhập được", call(
        "POST", "/auth/login", json={"username": new_user, "password": temp}), 401, "INVALID_CREDENTIALS")
    time.sleep(1)  # nhật ký ghi sau khi response đã gửi
    logs = expect("Admin xem nhật ký truy cập của vụ", call("GET", f"/admin/access-logs?caseId={case_id}&size=200",
                                                            admin), 200)
    actions = {(i["action"], i["result"]) for i in logs["items"]}
    step("Có ghi thao tác của thư ký trong vụ (ALLOW)", ("POST /cases/{case_id}/lots", "ALLOW") in actions)
    step("Có ghi cả thao tác bị từ chối của người ngoài vụ (DENY)",
         any(i["result"] == "DENY" and i["action"] == "GET /cases/{case_id}" for i in logs["items"]))
    denied = call("GET", "/admin/access-logs?result=DENY&size=5", admin).json()
    step("Lọc được thao tác bị từ chối", denied["total"] > 0 and all(i["result"] == "DENY" for i in denied["items"]),
         f"{denied['total']} lượt")

    passed = sum(1 for ok, _ in results if ok)
    failed = [name for ok, name in results if not ok]
    print(f"\n== Kết quả: {passed}/{len(results)} đạt, {len(failed)} lỗi — vụ {case_number}")
    for name in failed:
        print(f"   LỖI: {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
