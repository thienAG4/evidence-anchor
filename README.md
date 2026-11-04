# EvidenceChain

Lưu chứng bằng chứng số (ảnh, ghi âm, video, văn bản…) bằng **SHA-256** và ghi dấu lên testnet **Ethereum Sepolia**.
File gốc **không bao giờ lên blockchain** — chỉ có dấu vân tay (hash). Ai giữ file gốc và biên nhận đều có thể tự kiểm tra
file còn nguyên vẹn và đã tồn tại trước thời điểm block được ghi.

**Demo:** https://evidence-anchor.streamlit.app

> Đây là dự án học tập. Chỉ dùng **ví test** trên Sepolia, không dùng ví có tiền thật.

---

## 1. Cơ chế xử lý

### 1.1. Sơ đồ gộp hash

```
File 1 ─► H1 ─┐                         (t1 = lúc hash xong File 1)
     t1 ─► Ht1 ┴─► Ha = SHA256(H1 ‖ Ht1)
              ⏸ nghỉ ngẫu nhiên 1.00–3.00 giây
File 2 ─► H2 ─┐
     t2 ─► Ht2 ┴─► Hb = SHA256(H2 ‖ Ht2)
              ⏸ nghỉ ngẫu nhiên 1.00–3.00 giây
File 3 ─► H3 ─┐
     t3 ─► Ht3 ┴─► Hc = SHA256(H3 ‖ Ht3)

Ha, Hb, Hc (sắp theo Hi giảm dần) ─► Habc = SHA256(Ha ‖ Hb ‖ Hc)
                    tB = lúc Habc tính xong ─► HtB = SHA256(tB)
                                    Bundle = SHA256(Habc ‖ HtB)
```

### 1.2. Từng bước

| Bước | Công thức | Ghi chú |
|---|---|---|
| Hash file | `Hi = SHA256(nội dung file i)` | Đọc từng khúc 1MB → file lớn (video) không tốn RAM |
| Thời điểm hash | `ti` = giờ VN lúc hash xong, chính xác 1/100 giây | Dạng `2026-11-01T23:53:25.61+07:00`, do **hệ thống tự lấy**, người dùng không nhập |
| Hash thời điểm | `Hti = SHA256(ti)` | Chuỗi UTF-8 |
| Lá của file | `Ha = SHA256(Hi ‖ Hti)` | Gắn nội dung với thời điểm của chính file đó |
| Nghỉ | `sleep(random 1.00–3.00 s)` | Giữa 2 file liên tiếp, để mỗi file có mốc thời gian tách biệt |
| Gộp | `Habc = SHA256(Ha ‖ Hb ‖ …)` | Các lá **sắp theo Hi giảm dần (Z→A)** → thứ tự chọn file không ảnh hưởng kết quả |
| Bundle | `Bundle = SHA256(Habc ‖ SHA256(tB))` | `tB` = lúc Habc tính xong |

Ký hiệu `‖` là **nối 32 byte nhị phân** của từng hash (không phải nối chuỗi hex). Vì mỗi hash dài cố định 32 byte,
cách ghép không thể bị hiểu nhầm ranh giới. Toàn bộ nằm trong [`backend/app/core/hashing.py`](backend/app/core/hashing.py).

> Vì sao không dùng XOR / cộng / nhân để gộp? Các phép này không phải hàm băm: XOR làm 2 file trùng nhau tự triệt tiêu
> (H ⊕ H = 0) và có thể bị tấn công tìm bộ file khác cho cùng kết quả. Bước gộp cuối luôn là SHA-256.

### 1.3. Ghi lên Sepolia

Không dùng smart contract. Mỗi hash được ghi bằng **1 giao dịch 0 ETH gửi cho chính ví mình**, hash nằm trong trường
`data` (`0x` + hash). Mỗi lần nộp tạo **N + 1 giao dịch**:

- 1 giao dịch chứa **Bundle**
- N giao dịch, mỗi giao dịch chứa **Hi** (hash nội dung) của một file

Nếu một giao dịch file bị lỗi sau khi bundle đã lên chain, biên nhận vẫn được tạo và ghi lỗi tại file đó (không mất
dấu bundle đã trả phí). Xem [`backend/app/core/chain.py`](backend/app/core/chain.py).

### 1.4. Về thời gian

- `hashedAt`, `bundledAt` là **giờ của máy chủ** — hữu ích để mô tả quy trình, nhưng do hệ thống tự ghi.
- **Giờ của block** (`blockTimeVN`) mới là mốc do blockchain xác nhận: bằng chứng chắc chắn **đã tồn tại trước** thời điểm đó.

---

## 2. Biên nhận (receipt JSON)

```jsonc
{
  "bundleScheme": "per-file-time-v2",
  "algorithm": "SHA-256",
  "network": "Sepolia",
  "anchoredBy": "0x…",                 // ví đã ghi
  "submittedAt": "2026-11-01T23:53:25.61+07:00",
  "files": [
    {
      "fileName": "anhchup.jpg",
      "fileHash": "4c9b…",              // Hi
      "hashedAt": "2026-11-01T23:53:25.61+07:00",   // ti
      "timeHash": "…",                  // Hti
      "leafHash": "…",                  // Ha
      "sleepAfterSeconds": 2.25,
      "tx": { "txHash": "0x…", "explorerUrl": "https://sepolia.etherscan.io/tx/0x…",
              "blockNumber": 12042325, "blockTimeVN": "01/11/2026 23:53:48", "…": "…" }
    }
  ],
  "bundle": {
    "order": ["…"],                     // thứ tự Hi đã dùng khi gộp
    "habc": "…",
    "bundledAt": "2026-11-01T23:53:30.56+07:00",
    "bundleTimeHash": "…",
    "bundleHash": "a6b1…",
    "tx": { "txHash": "0x…", "explorerUrl": "…", "blockNumber": 12042324, "blockTimeVN": "…" }
  }
}
```

Mỗi lần tạo biên nhận thành công, một dòng tóm tắt được ghi vào `history.json` (tab **Lịch sử**).

## 3. Cách kiểm tra (tab "Kiểm tra tệp" hoặc tự làm tay)

1. Hash lại từng file gốc, so với `fileHash` trong biên nhận (so theo **hash**, đổi tên file không ảnh hưởng).
2. Từ `fileHash` + `hashedAt` + `bundledAt` trong biên nhận, tính lại `Ha…`, `habc`, `bundleHash` theo mục 1.2 — phải khớp.
   Nếu ai sửa thời gian hay hash trong biên nhận, bước này sẽ sai.
3. Mở `explorerUrl` trên Etherscan: giao dịch thành công, gửi từ **ví của hệ thống** (đối chiếu với địa chỉ ví công bố,
   không chỉ tin trường `anchoredBy` trong biên nhận), và **Input Data** = `0x` + hash tương ứng.

---

## 4. Cấu trúc dự án

```
evidence-anchor/
├── backend/
│   ├── app/                              # FastAPI
│   │   ├── main.py                       # tạo app, gắn router
│   │   ├── config.py                     # đọc .env
│   │   ├── labels.py                     # nhãn hiển thị (KHỚP/KHÁC...), trạng thái neo
│   │   ├── core/
│   │   │   ├── hashing.py                # Hash file/timestamp, bundle per-file-time-v2, hash tổng lô court-lot-v1
│   │   │   ├── merkle.py                 # Cây Merkle cho neo theo ngày
│   │   │   ├── signing.py, receipt.py    # Dựng + ký biên nhận (EIP-191)
│   │   │   ├── security.py               # Mật khẩu (scrypt), JWT
│   │   │   ├── file_types.py             # Chỉ nhận PDF, ảnh, video, âm thanh (đuôi + nội dung)
│   │   │   └── chain.py                  # Ghi hash lên Sepolia, kiểm tra giao dịch
│   │   ├── routers/                      # auth.py, submissions.py
│   │   ├── services/                     # auth, submission, anchor; legacy_receipt_service.py (bản Streamlit)
│   │   ├── workers/anchor_worker.py      # Tiến trình riêng: neo lên Sepolia, thử lại khi lỗi
│   │   ├── dependencies/                 # đăng nhập, phân quyền, kiểm tra file tải lên
│   │   ├── errors/, schemas/
│   │   └── db/
│   │       ├── models/                   # 13 entity, xem docs/entities.md
│   │       └── history.py                # Lịch sử biên nhận (history.json) — bản Streamlit
│   ├── alembic/                          # migration (có cấp quyền chỉ ghi thêm — F6)
│   ├── docker/postgres-init/             # tạo role evidence_app khi dựng DB lần đầu
│   ├── scripts/
│   │   ├── seed.py                       # tạo tài khoản + vụ án mẫu để test
│   │   └── demo_cli.py                   # Chạy thử bằng dòng lệnh (bản Streamlit)
│   ├── requirements.txt                  # Thư viện cho backend FastAPI
│   └── .env.example
├── docs/                                 # proposal, backlog, entities, api; postman/ (collection để test)
├── frontend/                             # Giao diện HTML/CSS/JS (xem frontend/README.md), backend phục vụ ở :8000
│   ├── pages/, assets/                   # trang đương sự + thư ký; assets/js/data/api.js gọi API
│   └── app.py                            # Giao diện Streamlit cũ: Tạo biên nhận / Kiểm tra tệp / Lịch sử
├── docker-compose.yml                    # PostgreSQL cho máy dev
├── requirements.txt                      # Để ở gốc vì Render / Streamlit Cloud đọc ở đây
└── render.yaml                           # Cấu hình deploy lên Render
```

API đã có đủ F1–F9 theo `docs/api.md`. Chưa làm: neo theo ngày (`ANCHOR_MODE=daily`), giao diện HTML thay Streamlit.

## 5. Chạy trên máy

Cần **Python 3.11 trở lên** (`streamlit==1.66.1` không cài được trên 3.10). Trên Windows có nhiều bản Python thì
dùng `py -3.13` để chọn đúng bản:

```bash
py -3.13 -m venv venv            # macOS/Linux: python3 -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

PowerShell chặn `activate` thì chạy thẳng bằng Python trong venv, không cần kích hoạt:
`venv\Scripts\python.exe -m streamlit run frontend/app.py`

Tạo file `.env` (đã nằm trong `.gitignore`, **không commit**):

```
SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
PRIVATE_KEY=0x...khóa_ví_test
```

Xin Sepolia ETH miễn phí từ một faucet cho ví test, rồi chạy:

```bash
streamlit run frontend/app.py    # giao diện web
python backend/scripts/demo_cli.py   # hoặc chạy thử dòng lệnh, ra receipt.json
```

### 5.1. Backend FastAPI + PostgreSQL

Cần Docker Desktop đang chạy. Mẫu `.env` đầy đủ: [`backend/.env.example`](backend/.env.example)
(thêm `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `RECEIPT_SIGNING_KEY`, `JWT_SECRET`, `ANCHOR_WALLET_ADDRESS`).

```powershell
venv\Scripts\python.exe -m pip install -r backend/requirements.txt
docker compose up -d db                                    # PostgreSQL ở localhost:5432
cd backend
..\venv\Scripts\python.exe -m alembic upgrade head         # tạo bảng + quyền
cd ..
venv\Scripts\python.exe backend/scripts/seed.py            # tài khoản test
venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend
```

Mở **http://localhost:8000** để vào giao diện (đăng nhập `duongsu / 1234` hoặc `thuky / 5678`),
http://localhost:8000/docs để xem API. Worker neo chạy ở **terminal khác** (cần `PRIVATE_KEY` có Sepolia ETH):

```powershell
cd backend
..\venv\Scripts\python.exe -m app.workers.anchor_worker
```

Không chạy worker thì biên nhận vẫn tạo được, chỉ ở trạng thái "Chờ neo".

Kiểm thử trọn quy trình lưu chứng (đăng nhập → nộp → tra cứu → chờ neo → tự kiểm tra biên nhận → phát hiện chỉnh sửa):

```powershell
venv\Scripts\python.exe backend/scripts/e2e_f1.py                     # tự tạo ảnh, ghi âm, PDF mẫu
venv\Scripts\python.exe backend/scripts/e2e_f1.py anh.jpg ghiam.m4a    # dùng file của bạn
```

Kiểm thử trọn quy trình tại Tòa (tạo vụ → lưu chứng → nạp lô → KHỚP/KHÁC/KHÔNG CÓ MỐC → xem kết quả → tính lại
→ giám định → kháng cáo, chốt hồ sơ → phúc thẩm đối chiếu → /verify → nhật ký truy cập). Mỗi lần chạy tạo 1 vụ mới:

```powershell
venv\Scripts\python.exe backend/scripts/e2e_court.py
```

Tài khoản có sẵn (sau khi chạy `seed.py`), đăng nhập `POST /auth/login` với `{username, password}`:

| Tên đăng nhập | Mật khẩu | Vai trò |
|---|---|---|
| `duongsu` | `1234` | Đương sự (nguyên đơn vụ mẫu) |
| `thuky` | `5678` | Thư ký TAND Quận 1 |
| `bidon` | `1234` | Đương sự (bị đơn) — tài khoản phụ để test |
| `luatsu` | `1234` | Luật sư — tài khoản phụ |
| `thamphan` | `5678` | Thẩm phán — tài khoản phụ |
| `thuky.phuctham` | `5678` | Thư ký TAND TP.HCM (phúc thẩm) — tài khoản phụ |
| `admin` | `5678` | Quản trị — tài khoản phụ |

Tất cả trừ admin và thư ký phúc thẩm đều tham gia vụ mẫu `01/2026/DS-ST`. Không có đăng ký hay OTP; tài khoản
mới do admin tạo (`POST /admin/users`).

File chứng cứ chỉ nhận **PDF, ảnh, video, âm thanh**; file khác (.exe, .zip, .docx…) bị từ chối kèm thông báo.

## 6. Deploy lên Render

1. Trên [Render](https://render.com): **New → Blueprint**, chọn repo này. Render đọc `render.yaml`.
2. Khi được hỏi, nhập `PRIVATE_KEY` (khóa ví test). `SEPOLIA_RPC_URL` đã có sẵn giá trị mặc định.
3. Đợi build xong, mở URL dịch vụ.

Lưu ý khi deploy:

- Gói free của Render có ổ đĩa **tạm thời**: `history.json` sẽ mất khi dịch vụ khởi động lại hoặc deploy lại.
- Ai có URL đều có thể bấm "Tạo biên nhận" và tiêu Sepolia ETH của ví test — chỉ để ví test, ít tiền.
- Gói free sẽ "ngủ" khi không có truy cập, lần mở đầu tiên có thể mất ~1 phút.

## 7. Deploy lên Streamlit Community Cloud

1. Vào [share.streamlit.io](https://share.streamlit.io), đăng nhập bằng GitHub.
2. **Create app → Deploy a public app from GitHub**:
   - Repository: `thienAG4/evidence-anchor`, Branch: `main`, Main file path: `frontend/app.py`
   - **Advanced settings → Python 3.12**, và ô **Secrets**:

     ```toml
     SEPOLIA_RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
     PRIVATE_KEY = "0x...khóa_ví_test"
     ```
3. Bấm **Deploy**. Streamlit Cloud cài `requirements.txt` ở thư mục gốc; các secret cấp cao nhất được đưa vào
   biến môi trường nên `backend/app/core/chain.py` đọc `os.environ` như khi chạy trên máy.

Các lưu ý về ổ đĩa tạm (`history.json`) và việc người khác tiêu ETH của ví test ở mục 6 cũng áp dụng ở đây.

## 8. Bảo mật

- Không bao giờ commit `.env` hay private key. Nếu lỡ commit, coi như khóa đã lộ và đổi ví.
- Hash từng file được ghi **công khai**: ai đã có sẵn một bản file có thể kiểm tra nó có trong hồ sơ hay không.
- Giữ file gốc cẩn thận — mất file gốc thì hash trên chain không còn để đối chiếu.
