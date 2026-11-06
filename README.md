# EvidenceChain

Hệ thống lưu chứng bằng chứng số (ảnh, ghi âm, video, văn bản) cho quy trình tố tụng dân sự. Mỗi file được băm
SHA-256, ghi vào nhật ký chỉ ghi thêm, rồi gom theo đợt và neo mã tổng hợp lên **Ethereum Sepolia**. Ai giữ file gốc
và biên nhận đều tự kiểm tra được file còn nguyên vẹn và đã tồn tại trước một block, không cần hỏi Tòa.

> Đây là đồ án học tập. Chỉ dùng **ví test** trên Sepolia, không dùng ví có tiền thật.

---

## 1. Giới thiệu

Chứng cứ điện tử dễ bị tranh cãi: file có bị sửa sau khi nộp không, nộp lúc nào, Tòa có giữ đúng bản đã nhận không.
EvidenceChain ghi lại **dấu vân tay** (hash) của file tại thời điểm lưu chứng và công khai bằng chứng đó trên chuỗi,
để bất kỳ ai cũng đối chiếu được sau này.

| Vai trò | Dùng hệ thống để |
|---|---|
| Đương sự | Lưu chứng file trước khi khởi kiện, nhận biên nhận, tự kiểm tra biên nhận |
| Thư ký Tòa | Nhận lô chứng cứ, đối chiếu file với bản đã lưu chứng, ghi kết quả |
| Thẩm phán, luật sư | Xem kết quả đối chiếu trong vụ (qua API) |
| Người kiểm tra độc lập | Kiểm tra biên nhận và file gốc trên trang công khai, hoặc tự tính lại theo `docs/test-vectors.json` |

Hash tính ở máy chủ: file được tải lên để băm rồi bỏ ngay, hệ thống không lưu nội dung file. Trên chuỗi chỉ có mã tổng
hợp của cả đợt, không có hash từng file hay thông tin người dùng.

## 2. Tính năng chính

Theo [`docs/proposal.md`](docs/proposal.md):

| Mã | Tính năng |
|---|---|
| F1 | Đương sự lưu chứng nhiều file một lần, nhận một mã biên nhận và mã riêng từng file |
| F2, F3 | Nộp lô chứng cứ tại Tòa; hệ thống tự so hash với bản đã lưu chứng (KHỚP / KHÁC BẢN LƯU CHỨNG / KHÔNG CÓ MỐC) |
| F4 | Giám định: so hash khi file đi, nhận, về |
| F5 | Xem kết quả trong phiên họp, xét xử |
| F6 | Nhật ký chỉ ghi thêm, không sửa, không xóa được |
| F7 | Gắn chứng cứ và bản lưu chứng với vụ án |
| F8 | Đăng nhập, phân quyền theo vụ, nhật ký truy cập |
| F9 | Chốt hồ sơ khi kháng cáo, phúc thẩm đối chiếu lại |

Phần neo và kiểm chứng:

- **Neo theo đợt** lên Sepolia, có hai chế độ: neo ngay sau mỗi lần ghi (demo) hoặc mỗi ngày một đợt. Có nút
  **Neo ngay** để khóa sớm, và tự **neo bù** khi worker tắt hay mất mạng.
- **Biên nhận có chữ ký** EIP-191 trên từng bản ghi và trên cả biên nhận.
- **Trang tự kiểm tra công khai**: kiểm 13 mục, từ chữ ký tới giao dịch trên chuỗi, không cần tài khoản.
- **OpenTimestamps**: trình duyệt của đương sự tự đóng dấu hash file lên Bitcoin, độc lập với Tòa và Ethereum.
- **Chống lỗi khi neo**: phát hiện ví bị dùng bên ngoài thì dừng, gửi lại giao dịch kẹt, giới hạn số lần gửi lại.

## 3. Kiến trúc

```
                    ┌───────────── Trình duyệt (HTML/CSS/JS thuần) ─────────────┐
                    │  đương sự · thư ký · trang kiểm tra công khai             │
                    └──────┬───────────────────────────────────────┬────────────┘
                           │ REST API                              │ hash đã trộn nonce
                           ▼                                       ▼
   ┌──────────────── FastAPI ────────────────┐         Máy chủ lịch OpenTimestamps ──► Bitcoin
   │ băm file, dựng biên nhận, ký EIP-191     │
   │ /verify kiểm biên nhận                    │
   └──────┬───────────────────────────────────┘
          │ chỉ ghi thêm
          ▼
   PostgreSQL ── log_record (bản ghi 164 byte nối chuỗi), anchor_batch, chain_tx, ots_stamp ...
          ▲
          │ tiến trình riêng, nơi duy nhất gửi giao dịch
   Worker neo ── chốt đợt, dựng cây Merkle, gửi ANCH ──► Ethereum Sepolia (theo dõi tới FINALIZED)
```

| Lớp | Công nghệ |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL 16 (Docker), tài khoản ứng dụng chỉ có quyền SELECT, INSERT trên bảng nhật ký |
| Chuỗi | web3.py 8, eth-account (EIP-191), Sepolia qua RPC công khai |
| OpenTimestamps | thư viện `opentimestamps` (server), tự ghép file .ots trong trình duyệt (`frontend/assets/js/data/ots.js`) |
| Frontend | HTML, CSS, JavaScript thuần, không cần build; backend phục vụ luôn thư mục `frontend/` |

## 4. Cơ chế kỹ thuật

Số nguyên luôn là big-endian không dấu. Ký hiệu `‖` là nối **byte nhị phân** (không nối chuỗi hex). Mọi công thức dưới
đây có dữ liệu mẫu và mẫu phải từ chối trong [`docs/test-vectors.json`](docs/test-vectors.json).

### 4.1. Hash file và bundle

| Bước | Công thức |
|---|---|
| Hash file | `Hi = SHA256(file)`, đọc theo khúc 1 MB |
| Thời điểm | `ti` = giờ máy chủ lúc băm xong, ví dụ `2026-11-06T03:15:48.50+07:00`; người dùng không nhập |
| Lá của file | `Ha = SHA256(Hi ‖ SHA256(ti))` |
| Gộp lần nộp | `Habc = SHA256(Ha ‖ Hb ‖ …)`, lá sắp theo Hi giảm dần nên thứ tự chọn file không ảnh hưởng |
| Bundle | `Bundle = SHA256(Habc ‖ SHA256(tB))`, `tB` là lúc gộp xong |

Giữa hai file, hệ thống nghỉ ngẫu nhiên 1 đến 3 giây để mỗi file có mốc thời gian riêng. Lô chứng cứ tại Tòa dùng công
thức `court-lot-v1`: thêm `SHA256("nơi nộp|số file")` vào bundle. Bundle nằm trong biên nhận và được ký, không lên chuỗi.
Mã nguồn: [`backend/app/core/hashing.py`](backend/app/core/hashing.py).

### 4.2. Bản ghi 164 byte và chuỗi hash

Mỗi sự kiện (A lưu chứng, E đối chiếu, C giám định, D chốt hồ sơ) là một bản ghi dài cố định:

```
"EVC-REC-v1" 10 | seq u64 | type u8 | fileHash 32 | caseRef 32 | actorRef 32 | ts u64 | result u8 | refSeq u64 | prevRecordHash 32
```

`recordHash = SHA256(164 byte)`. Mỗi bản ghi giữ hash của bản ghi trước, nên sửa hay xóa một bản ghi cũ làm đứt
cả chuỗi phía sau. Mã nguồn: [`backend/app/core/record.py`](backend/app/core/record.py).

### 4.3. Cây Merkle hai tầng

Theo RFC 6962: lá = `SHA256(0x00 ‖ recordHash)`, nút trong = `SHA256(0x01 ‖ trái ‖ phải)`, tầng lẻ thì nút cuối đẩy
thẳng lên. Bản ghi trong đợt được nhóm theo người ghi. Mỗi nhóm cho một `subRoot`, rồi tầng trên dựng cây trên các
`subRoot` để ra **root của đợt**. Biên nhận chứa `groupPath` (lá tới subRoot) và `batchPath` (subRoot tới root).
Mã nguồn: [`backend/app/core/merkle.py`](backend/app/core/merkle.py).

### 4.4. Dòng ghi lên chuỗi

Mỗi dòng là `data` của một giao dịch 0 ETH từ ví neo gửi cho chính nó: nhãn 4 byte ‖ phiên bản 1 byte ‖ nội dung.

| Nhãn | Byte | Nội dung |
|---|---|---|
| ANCH | 93 | `batchId u64 ‖ fromSeq u64 ‖ toSeq u64 ‖ prevRoot 32 ‖ root 32` |
| KEYR | 37 | `keyId u32 ‖ địa chỉ khóa ký biên nhận 20 ‖ fromSeq u64`; giao dịch đầu tiên của ví |
| NOOP | 13 | `nonce u64` của giao dịch kẹt bị thay |

Quy tắc liền mạch: đợt 1 có `prevRoot` toàn 0 và `fromSeq = 1`; đợt sau có `batchId` tăng 1, `prevRoot` bằng root đợt
trước, `fromSeq` bằng `toSeq` đợt trước cộng 1. Người kiểm tra nhờ đó phát hiện được bản ghi bị bỏ sót hoặc bị neo hai
lần. Mã nguồn: [`backend/app/core/payload.py`](backend/app/core/payload.py),
[`anchor_payload.py`](backend/app/core/anchor_payload.py).

### 4.5. Chữ ký biên nhận

Khóa ký biên nhận (EIP-191, secp256k1) khác khóa ví neo. Nội dung ký dài cố định 58 byte:

```
"EVC-RECEIPT-v1" 14 | keyId u32 | seq u64 | recordHash 32
```

Biên nhận có hai lớp chữ ký: mỗi file một chữ ký trên bản ghi của nó (`files[].recordSignature`), và một chữ ký trên
cả biên nhận (recordHash thay bằng `SHA256(JSON biên nhận)`) để giữ bundle, tên file, giờ có phần trăm giây khỏi bị
sửa. Người kiểm tra khôi phục địa chỉ từ chữ ký rồi so với địa chỉ đã công bố (`GET /signing-key`, dòng KEYR).

### 4.6. Vòng đời một đợt neo

```
PENDING (chốt đợt, cấp nonce, lưu đúng byte sẽ gửi) → SUBMITTED → CONFIRMED (lên khối) → FINALIZED (khoảng 13 phút)
```

Biên nhận chỉ **hoàn chỉnh** khi block đã chốt. Giao diện hiện ba bước: Đã ghi nhận, Đã khóa, Tòa đã kiểm tra.

| `ANCHOR_MODE` | Khi nào chốt đợt |
|---|---|
| `per_submission` | Ngay khi có bản ghi mới: API gửi `NOTIFY anchor_wake` lúc commit, worker đang `LISTEN` dậy chốt đợt và gửi giao dịch (gom các lần ghi trong 1 giây). Không có bản ghi thì worker vẫn chạy mỗi `ANCHOR_INTERVAL_SECONDS` (15 giây) để theo dõi giao dịch đã gửi |
| `daily` | Mỗi ngày (giờ Việt Nam) một đợt ở mốc `ANCHOR_DAILY_CUTOFF` (mặc định 23:59); ngày bị lỡ thì neo bù, vẫn mỗi ngày một đợt; ngày không có bản ghi thì không neo |

Nút **Neo ngay** trên trang chi tiết biên nhận (`POST /anchor/now`) cho worker chốt các bản ghi đang chờ ở vòng kế,
không đợi mốc ngày. `GET /anchor/schedule` cho biết mốc khóa kế tiếp.

### 4.7. Chống lỗi khi neo

| Tình huống | Cách xử lý |
|---|---|
| Ví bị dùng ngoài worker | Nonce trên mạng vượt nonce đã cấp: dừng job neo, chờ người vận hành |
| Giao dịch thất bại trên chuỗi | Dừng job neo |
| Mất mạng | Vòng worker lỗi, bản ghi vẫn chờ, vòng sau làm tiếp; giao dịch đã ký được lưu trước khi phát nên không cấp trùng nonce |
| Giao dịch kẹt | Quá `ANCHOR_RETRY_SECONDS` thì gửi lại cùng payload, cùng nonce, phí gấp đôi; quá `ANCHOR_MAX_REPLACEMENTS` lần thì dừng |
| Khối bị xếp lại | Trước khi ghi FINALIZED, đọc lại giao dịch từ chuỗi, không tin số khối đã lưu |

NOOP không gửi tự động: thay một ANCH kẹt bằng NOOP sẽ bỏ đợt đó khỏi chuỗi và làm đứt quy tắc liền mạch.

### 4.8. OpenTimestamps

Theo tài liệu kỹ thuật mục 6.9, chỉ cho bản ghi A (lưu chứng của đương sự):

1. Sau khi lưu chứng, trình duyệt lấy `fileHash` trong biên nhận, trộn nonce 16 byte ngẫu nhiên, băm lại rồi gửi tới
   4 máy chủ lịch. Máy chủ lịch không thấy file, cũng không thấy `fileHash`.
2. Máy chủ lịch chặn CORS thì gửi qua `POST /ots/relay/{i}`; máy chủ Tòa cũng chỉ thấy giá trị đã trộn nonce.
3. Trình duyệt ghép file .ots chuẩn (đọc được bằng `ots verify` hoặc opentimestamps.org), gửi bản chờ lên server và cho
   đương sự tải về giữ riêng.
4. Worker nâng cấp mỗi giờ (`OTS_UPGRADE_SECONDS`), ghi log ERROR nếu quá 48 giờ chưa có xác nhận của Bitcoin.

## 5. Biên nhận và cách tự kiểm tra

Biên nhận tải về từ trang chi tiết (`GET /receipts/{code}`) có dạng:

```jsonc
{
  "receipt": {                         // phần được ký
    "receiptCode": "TX-0042", "type": "SELF", "submittedAt": "…", "bundleScheme": "per-file-time-v2",
    "files": [{ "fileCode": "TX-0042-1", "fileName": "…", "fileHash": "…", "hashedAt": "…", "timeHash": "…",
                "leafHash": "…", "seq": 192, "recordHash": "…", "recordSignature": "0x…" }],
    "bundle": { "habc": "…", "bundledAt": "…", "bundleHash": "…" },
    "signer": { "algorithm": "EIP-191", "keyNo": 1, "address": "0x…" }
  },
  "signature": "0x…",                  // chữ ký trên cả biên nhận
  "anchor": {                          // có khi block đã chốt
    "records": [{ "fileCode": "…", "seq": 192, "raw": "164 byte hex", "groupPath": [], "batchPath": [],
                  "root": "…", "payload": "ANCH 93 byte hex", "txHash": "0x…", "explorerUrl": "…" }]
  },
  "ots": [{ "fileCode": "…", "status": "PENDING", "ots": "base64" }]
}
```

Trang **Kiểm tra biên nhận** (`frontend/pages/public/verify-receipt.html`, gọi `POST /verify`) không cần đăng nhập.
Đưa biên nhận và file gốc vào, hệ thống kiểm:

| # | Mục kiểm |
|---|---|
| 1 | Chữ ký hệ thống trên biên nhận |
| 2 | Chữ ký hệ thống trên bản ghi của từng file (58 byte) |
| 3 | File tải lên khớp hash trong biên nhận |
| 4 | Tính lại Hti, Ha từng file |
| 5 | Tính lại Habc, Bundle |
| 6 | OpenTimestamps: file .ots đóng dấu đúng hash từng file (khi biên nhận có phần `ots`) |
| 7 | Bản ghi 164 byte của từng file chứa đúng hash file |
| 8 | Đường dẫn Merkle từ từng bản ghi tới root đợt neo |
| 9 | Dữ liệu đợt neo (ANCH) chứa root và khoảng số thứ tự có bản ghi |
| 10 | Giao dịch neo tồn tại và thành công |
| 11 | Block chứa giao dịch đã chốt (finalized) |
| 12 | Input Data của giao dịch bằng dữ liệu đợt neo |
| 13 | Giao dịch gửi từ ví của hệ thống |

Không đạt thì trang chỉ ra mục và file sai, nhưng không kết luận ai đã sửa: nén hay chuyển mã file cũng cho kết quả này.

Kiểm tra không cần hệ thống:

- Tính lại hash, bundle, bản ghi, cây Merkle theo `docs/test-vectors.json`, viết bằng ngôn ngữ nào cũng được.
- Mở `explorerUrl` trên Etherscan: Input Data phải bằng `payload`, gửi từ địa chỉ ví neo đã công bố.
- Đối chiếu file .ots với Bitcoin bằng opentimestamps.org hoặc lệnh `ots verify`.

## 6. Cấu trúc thư mục

```
evidence-anchor/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, labels.py
│   │   ├── core/
│   │   │   ├── hashing.py            # hash file, bundle per-file-time-v2, court-lot-v1
│   │   │   ├── record.py             # bản ghi 164 byte EVC-REC-v1, kiểm chuỗi hash
│   │   │   ├── log_record.py         # chuyển kiểu giữa model và record.py
│   │   │   ├── merkle.py             # cây Merkle RFC 6962 hai tầng
│   │   │   ├── payload.py            # ANCH 93 byte, quy tắc liền mạch
│   │   │   ├── anchor_payload.py     # KEYR, NOOP
│   │   │   ├── signing.py, receipt.py   # chữ ký EIP-191 58 byte, dựng biên nhận
│   │   │   ├── chain.py, chain_reader.py  # ký, gửi, đọc giao dịch Sepolia
│   │   │   ├── ots.py                # đọc, nâng cấp file .ots
│   │   │   ├── security.py           # mật khẩu scrypt, JWT
│   │   │   └── file_types.py         # chỉ nhận PDF, ảnh, video, âm thanh (đuôi và nội dung)
│   │   ├── routers/                  # auth, submissions, clerk, cases, lots, dossiers, verify, admin, anchoring
│   │   ├── services/                 # nghiệp vụ: submission, lot, appraisal, dossier, anchor, ots, verify ...
│   │   ├── workers/
│   │   │   ├── anchor_worker.py      # tiến trình neo (và nâng cấp OpenTimestamps mỗi giờ)
│   │   │   └── ots_upgrade.py        # chạy nâng cấp OpenTimestamps một lần
│   │   ├── db/models/                # 17 bảng, xem docs/entities.md
│   │   ├── dependencies/, errors/, schemas/
│   ├── alembic/                      # migration, gồm cấp quyền chỉ ghi thêm (F6)
│   ├── docker/postgres-init/         # tạo role evidence_app khi dựng DB lần đầu
│   ├── scripts/
│   │   ├── seed.py                   # tài khoản và vụ án mẫu
│   │   ├── gen_test_vectors.py       # sinh docs/test-vectors.json
│   │   └── e2e_f1.py, e2e_court.py   # kiểm thử trọn quy trình qua API
│   ├── tests/                        # test_vectors.py, test_ots.py, test_anchor_worker.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                         # xem frontend/README.md
│   ├── pages/                        # auth, litigant (lưu chứng, biên nhận), clerk, public (kiểm tra biên nhận)
│   └── assets/                       # css, js (data/api.js gọi API, data/ots.js đóng dấu OpenTimestamps)
├── docs/                             # proposal, backlog, entities, api, test-vectors.json, postman/, demo/
└── docker-compose.yml                # PostgreSQL cho máy dev
```

## 7. Cài đặt và chạy

### 7.1. Yêu cầu

- Python 3.12
- Docker Desktop (để chạy PostgreSQL)
- Ví test trên Sepolia có ít ETH (xin từ faucet), chỉ cần nếu muốn neo thật

### 7.2. Cấu hình

Sao chép [`backend/.env.example`](backend/.env.example) thành `.env` ở thư mục gốc repo rồi điền giá trị. File `.env`
đã nằm trong `.gitignore`, không commit.

| Biến | Ý nghĩa |
|---|---|
| `DATABASE_URL` | Tài khoản ứng dụng `evidence_app` (không UPDATE, DELETE được bảng nhật ký) |
| `MIGRATION_DATABASE_URL` | Chủ sở hữu bảng, chỉ để chạy migration |
| `SEPOLIA_RPC_URL` | RPC Sepolia, mặc định RPC công khai |
| `PRIVATE_KEY` | Khóa ví neo (ví test). Trống thì không neo, biên nhận ở trạng thái "Chờ neo" |
| `ANCHOR_WALLET_ADDRESS` | Địa chỉ công khai của ví neo, để `/verify` kiểm ai gửi giao dịch |
| `RECEIPT_SIGNING_KEY` | Khóa ký biên nhận, khác khóa ví neo |
| `RECEIPT_KEY_NO`, `RECEIPT_SIGNER_ADDRESS` | Số khóa ký và địa chỉ đã công bố (tùy chọn) |
| `JWT_SECRET` | Khóa ký phiên đăng nhập |
| `ANCHOR_MODE` | `per_submission` (mặc định) hoặc `daily` |
| `ANCHOR_DAILY_CUTOFF` | Mốc khóa mỗi ngày ở chế độ `daily`, mặc định `23:59` |
| `ANCHOR_INTERVAL_SECONDS`, `ANCHOR_RETRY_SECONDS`, `ANCHOR_MAX_REPLACEMENTS` | Chu kỳ worker, thời gian coi là kẹt, số lần gửi lại tối đa |
| `OTS_UPGRADE_SECONDS`, `OTS_ALARM_HOURS` | Chu kỳ nâng cấp OpenTimestamps (3600), ngưỡng báo động (48) |
| `REQUIRE_ANCHOR_BEFORE_VERIFY` | `true`: thư ký chỉ đối chiếu biên nhận đã neo |

### 7.3. Chạy trên máy

```powershell
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r backend/requirements.txt
docker compose up -d db                                   # PostgreSQL ở localhost:5432
cd backend
..\venv\Scripts\python.exe -m alembic upgrade head        # tạo bảng và phân quyền
..\venv\Scripts\python.exe scripts/seed.py                # tài khoản và vụ án mẫu
cd ..
venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend
```

Mở **http://localhost:8000** để vào giao diện, **http://localhost:8000/docs** để xem API. Worker neo chạy ở một
terminal khác (cần `PRIVATE_KEY` có Sepolia ETH):

```powershell
cd backend
..\venv\Scripts\python.exe -m app.workers.anchor_worker
```

Không chạy worker thì vẫn lưu chứng và nhận biên nhận bình thường, chỉ dừng ở trạng thái "Chờ neo".

### 7.4. Tài khoản test

Tạo bởi `seed.py`:

| Tên đăng nhập | Mật khẩu | Vai trò |
|---|---|---|
| `duongsu` | `1234` | Đương sự (nguyên đơn vụ mẫu) |
| `thuky` | `5678` | Thư ký TAND Quận 1 |
| `bidon` | `1234` | Đương sự (bị đơn) |
| `luatsu` | `1234` | Luật sư |
| `thamphan` | `5678` | Thẩm phán |
| `thuky.phuctham` | `5678` | Thư ký TAND TP.HCM (phúc thẩm) |
| `admin` | `5678` | Quản trị |

Đương sự và thư ký có giao diện web; thẩm phán, luật sư và admin dùng API. Không có đăng ký hay OTP: tài khoản mới
do admin tạo (`POST /admin/users`).

## 8. Kiểm thử

**Video demo** ([`docs/demo/EvidenceChain-demo-tong-hop.mp4`](docs/demo/EvidenceChain-demo-tong-hop.mp4), khoảng
2 phút): chạy thật trên Chrome với ví neo Sepolia và máy chủ lịch OpenTimestamps, gồm 5 phần:

1. Lưu chứng 2 file; trình duyệt tự đóng dấu OpenTimestamps, tải file .ots.
2. Bấm Neo ngay: đợt neo lên Sepolia, trang chuyển sang "Đã neo, chờ chốt".
3. Chế độ neo theo ngày: không bấm gì, đúng mốc khóa thì hệ thống tự neo (UI-12).
4. Biên nhận đã chốt: tự kiểm tra trên trang công khai, đạt 13/13 mục (UI-16).
5. Đưa vào file bị sửa 1 bit: báo không hợp lệ, chỉ đúng file đó.

Video ghép từ các khung hình chụp sau mỗi thao tác; vòng tròn cam là chỗ bấm chuột, nhãn đen là thao tác.

```powershell
cd backend
..\venv\Scripts\python.exe -m pytest tests/test_vectors.py tests/test_ots.py
```

Kiểm định dạng dữ liệu theo `docs/test-vectors.json` (hash, bundle, bản ghi, Merkle, ANCH/KEYR/NOOP, chữ ký) và đọc,
kiểm file .ots. Không cần database hay mạng.

Worker neo được kiểm bằng chuỗi giả trên một **database trống riêng**, không gửi giao dịch thật. Các kịch bản gồm:
ranh giới ngày, neo bù, ngày trống, Neo ngay, mất mạng, giao dịch kẹt, giao dịch lạ, lưu và nâng cấp OpenTimestamps.

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://evidence_owner:owner_dev_pw@localhost:5432/ec_test"
..\venv\Scripts\python.exe -m pytest tests/test_anchor_worker.py
```

Kiểm thử trọn quy trình qua API, khi server đang chạy:

```powershell
venv\Scripts\python.exe backend/scripts/e2e_f1.py --anchor-timeout 1500   # lưu chứng → neo thật → tự kiểm tra → phát hiện sửa
venv\Scripts\python.exe backend/scripts/e2e_court.py                      # quy trình tại Tòa, mỗi lần chạy tạo một vụ mới
```

`e2e_f1.py` cần worker neo đang chạy để chờ biên nhận hoàn chỉnh; `--anchor-timeout 0` thì bỏ qua bước neo.

## 9. Tài liệu liên quan

| File | Nội dung |
|---|---|
| [`docs/proposal.md`](docs/proposal.md) | Đề xuất tính năng F1–F9 |
| [`docs/backlog.md`](docs/backlog.md) | Backlog |
| [`docs/api.md`](docs/api.md) | Danh sách API, quyền, input, output, mã lỗi |
| [`docs/entities.md`](docs/entities.md) | Các bảng, cột, quan hệ, luồng worker neo |
| [`docs/test-vectors.json`](docs/test-vectors.json) | Dữ liệu mẫu và mẫu phải từ chối, cho người viết lại thuật toán |
| [`docs/postman/`](docs/postman) | Collection Postman để gọi thử API |
| [`docs/demo/`](docs/demo) | Video demo 5 phần (mục 8) |
| [`frontend/README.md`](frontend/README.md) | Cấu trúc giao diện, cách chạy riêng frontend |

## 10. Phạm vi và giới hạn của đồ án

- Neo ngay sau mỗi lần ghi (`per_submission`) là giả lập cho demo; thiết kế thật là mỗi ngày một đợt (`daily`, đã có).
- Chỉ chạy trên testnet Sepolia. Ví neo và khóa ký là khóa test trên máy dev, chưa có quản lý khóa (HSM, KMS).
- KREV (thu hồi khóa ký) và WALL (đổi ví neo) mới có trong đặc tả, chưa có luồng xử lý.
- OpenTimestamps đã đóng dấu và chờ trên máy chủ lịch thật; bản hoàn chỉnh cần Bitcoin xác nhận sau vài giờ.
- Đăng nhập VNeID chưa có; thẩm phán, luật sư, admin chưa có giao diện web.

## 11. Bảo mật

- Không commit `.env`, private key hay khóa ký. Lỡ commit thì coi như khóa đã lộ, đổi ví và đổi khóa.
- Hash trên chuỗi là dữ liệu công khai vĩnh viễn. Hệ thống chỉ neo mã tổng hợp của đợt, nhưng ai có sẵn một bản file và
  biên nhận vẫn kiểm được file đó đã được lưu chứng.
- Giữ file gốc cẩn thận: mất file gốc thì không còn gì để đối chiếu với hash.
- File .ots và biên nhận nên lưu cùng file gốc; các file này không chứa nội dung file.
