# API

## Quy ước chung

Nhãn kết quả (DB lưu giá trị bên trái, API và giao diện hiển thị nhãn — xem `backend/app/labels.py`):

| DB | Với file | Với lô, giám định, hồ sơ chốt |
|---|---|---|
| `UNCHANGED` | KHỚP BẢN LƯU CHỨNG | KHỚP BẢN ĐÃ GHI |
| `CHANGED` | KHÁC BẢN LƯU CHỨNG | KHÁC BẢN ĐÃ GHI |
| `NO_BASELINE` | KHÔNG CÓ MỐC ĐỂ SO | không có |

- Mọi response kết quả đều **không chứa mã hash**, có `checkedAt` và `disclaimer`: "Chỉ so với bản đã lưu, không xác định thật giả."
  Ngoại lệ: biên nhận của chính đương sự (`GET /receipts/{code}`) và `POST /verify` có hash để tự kiểm tra.
- Lỗi: `{ "error": { "code", "message" } }`. Lỗi file chung: `FILE_REQUIRED`, `FILE_TOO_LARGE`, `TOO_MANY_FILES`.
- File gửi lên (multipart) được **băm theo luồng rồi bỏ**, không ghi ra đĩa, không lưu DB.
- Chỉ nhận **PDF, ảnh, video, âm thanh** (kiểm cả đuôi file lẫn nội dung đầu file); file khác (.exe, .zip, .docx,
  .txt…) hoặc file bị đổi đuôi → `400 FILE_TYPE_NOT_ALLOWED`. Một file bị từ chối thì cả lần gửi bị từ chối.
- Các thao tác "tính lại" (`/checks`) không sửa bản ghi cũ, chỉ ghi thêm 1 dòng `IntegrityCheck`.

## Đăng nhập

Không có đăng ký hay OTP: mọi người dùng tài khoản có sẵn (seed hoặc admin tạo), đăng nhập bằng tên đăng nhập +
mật khẩu, ví dụ `duongsu / 1234` (đương sự), `thuky / 5678` (thư ký).

| Endpoint | Ai gọi | Request | Response | Lỗi riêng |
|---|---|---|---|---|
| POST /auth/login | PUBLIC | `{username, password}` | 200 `{token, user}` | INVALID_CREDENTIALS |
| POST /auth/logout | mọi vai trò | không | 204 | |
| GET /me | mọi vai trò | không | 200 `{id, fullName, role}` | |

## Lưu chứng (đương sự)

| Endpoint | Ai gọi | Request | Response | Lỗi riêng |
|---|---|---|---|---|
| POST /submissions | PARTY | `files[]` | 202 `{receiptCode, status: PENDING_ANCHOR, submittedAt, files:[{fileName, fileCode, hashedAt}]}` | lỗi file chung |
| GET /submissions | PARTY | `page` | 200 danh sách biên nhận của mình (kèm `status`) | |
| POST /submissions/lookup | PARTY | `file` | 200 `{receiptCode, fileCode, hashedAt}`; chỉ tìm trong biên nhận của chính mình | RECORD_NOT_FOUND |
| GET /receipts/{code} | PARTY (của mình) | không | 200 biên nhận JSON có chữ ký hệ thống (có hash để tự kiểm tra); khi ANCHORED có thêm `anchor: {mode, txHash, explorerUrl, blockTime, records: [{fileCode, seq, raw (164 byte, hex), recordHash, batchNo, fromSeq, groupIndex, leafIndex, leafHash, groupPath, batchPath, root, payload (hex), txHash, blockNumber, blockTime, finalized, explorerUrl}]}` (mỗi file 1 bản ghi A) | RECEIPT_NOT_FOUND |
| GET /signing-key | PUBLIC | không | 200 `{algorithm: "EIP-191", keyNo, address}` để tự kiểm chữ ký biên nhận (khôi phục địa chỉ từ chữ ký rồi so với `address`) | |

`status` suy ra từ `AnchorLeaf` → `AnchorBatch` → `ChainTx` → `ChainTxResult`: `PENDING_ANCHOR` / `ANCHORED` / `ANCHOR_FAILED`.

`GET /submissions` và `GET /receipts/{code}` (trường `view`) có thêm kết quả Tòa đối chiếu từng file:
`files: [{fileCode, fileName, hashedAt, result: {value, label, checkedAt} | null, phase}]`, `checked`, `anchoredAt`.

## Giao diện thư ký: đối chiếu biên nhận lưu chứng

Thư ký chỉ thấy biên nhận của đương sự (PLAINTIFF, DEFENDANT, LAWYER) trong các vụ mà mình là CLERK. Không có mã hash.

| Endpoint | Ai gọi | Request | Response | Lỗi riêng |
|---|---|---|---|---|
| GET /clerk/receipts | CLERK | không | 200 `{items: [biên nhận + kết quả từng file]}` | |
| GET /clerk/receipts/{code} | CLERK | không | 200 | RECEIPT_NOT_FOUND |
| POST /clerk/receipts/{code}/compare | CLERK | `fileCode`, `file` | 200 `{fileCode, value, label}` — chỉ xem trước, không ghi | INVALID_STATE (chưa neo), FILE_CODE_NOT_FOUND |
| POST /clerk/receipts/{code}/verifications | CLERK | `phase`, `meta` (JSON `[{fileCode}]` cùng thứ tự `files[]`), `files[]` | 201 `{results: [{fileCode, result}]}` — máy chủ băm lại, ghi thêm IntegrityCheck kèm giai đoạn | INVALID_STATE, META_MISMATCH, FILE_CODE_NOT_FOUND |
| GET /clerk/litigants | CLERK | không | 200 `{items: [{username, fullName, email, receiptCount, fileCount, lastSubmittedAt}]}` | |

Quy tắc:
- Chỉ đối chiếu được biên nhận đã neo (`REQUIRE_ANCHOR_BEFORE_VERIFY=true`, mặc định).
- Mỗi file chỉ đối chiếu với bản lưu chứng **1 lần**: file đã có kết quả thì `compare` và `verifications` báo
  `409 INVALID_STATE` (UI-32).
- Lưu từng phần được (đối chiếu dở dang), nhưng các lần sau phải **cùng giai đoạn** với lần đầu, khác thì `409` (UI-33).
- Biên nhận có `checkedCount` (số file đã đối chiếu) và `checked = true` chỉ khi đủ n/n file (UI-17).

## Vụ án và người tham gia

| Endpoint | Ai gọi | Request | Response | Lỗi riêng |
|---|---|---|---|---|
| POST /cases | CLERK | `{caseNumber, title, courtName}` | 201 | CASE_EXISTS |
| GET /cases | mọi vai trò | không | 200 chỉ vụ mình tham gia | |
| GET /cases/{id} | người trong vụ | không | 200 | NOT_CASE_PARTICIPANT |
| PATCH /cases/{id} | CLERK | `{status, appealType}` | 200 | INVALID_STATE |
| GET /users/lookup?username= (hoặc ?email=) | CLERK | không | 200 `{id, username, fullName, role}` | USER_NOT_FOUND |
| POST /cases/{id}/participants | CLERK | `{userId, roleInCase}` | 201 | PARTICIPANT_EXISTS |
| GET /cases/{id}/participants | CLERK, JUDGE | không | 200 | |
| DELETE /cases/{id}/participants/{pid} | CLERK | không | 204 | |

## Nộp lô tại Tòa và xem kết quả

| Endpoint | Ai gọi | Request | Response | Lỗi riêng |
|---|---|---|---|---|
| GET /baselines/{fileCode} | CLERK | không | 200 `{hashedAt, ownerName}`; không có file, không có hash | FILE_CODE_NOT_FOUND |
| POST /cases/{id}/lots | CLERK | `place` (trống: tòa của thư ký), `meta` (JSON `[{fileCode}]` cùng thứ tự `files[]`, fileCode có thể trống; bỏ cả `meta` = mọi file không có mã), `files[]` | 202 `{receiptCode, lotNo, receivedAt, place, fileCount, status, files:[{fileName, result}]}` | FILE_CODE_NOT_FOUND (mã sai thì báo lỗi, không lưu, không so), META_MISMATCH, CASE_CLOSED |
| GET /cases/{id}/lots | PARTY, CLERK, JUDGE trong vụ | không | 200 các lô kèm kết quả từng file và cả lô, ngày giờ, nơi nộp, số lượng, checkedAt, disclaimer | |
| GET /cases/{id}/lots/{lotId} | như trên | không | 200 | LOT_NOT_FOUND |
| POST /cases/{id}/lots/{lotId}/checks | CLERK | `files[]` (file chọn lại trong hồ sơ) | 200 `{result: KHỚP / KHÁC BẢN ĐÃ GHI, checkedAt}`; tính lại hash tổng từ giờ, nơi, số lượng đã lưu; không tạo lô mới, ghi thêm 1 IntegrityCheck | LOT_NOT_FOUND |
| POST /cases/{id}/evidence/{fid}/checks | CLERK | `file` | 200 `{result, checkedAt}`; ghi thêm 1 IntegrityCheck | EVIDENCE_NOT_FOUND |

Cách so khi nộp lô: có fileCode thì so Hi với bản lưu chứng, bằng nhau là `UNCHANGED`, khác là `CHANGED`;
không có fileCode thì `NO_BASELINE` và hash lúc nhận làm mốc.

## Giám định (Thư ký ghi thay)

| Endpoint | Ai gọi | Request | Response | Lỗi riêng |
|---|---|---|---|---|
| POST /cases/{id}/evidence/{fid}/appraisal-steps | CLERK | `step` (SEND / RETURN), `file` | 201 `{step, result, recordedAt}`. SEND chỉ ghi được khi file còn khớp bản đã ghi lúc nhận; RETURN khác thì vẫn ghi, kết quả KHÁC BẢN ĐÃ GHI | FILE_CHANGED_SINCE_RECEIPT, INVALID_STATE (RETURN trước SEND) |
| GET /cases/{id}/evidence/{fid}/appraisal-steps | người trong vụ | không | 200 các bước, kết quả, ngày giờ | |

## Chốt hồ sơ (Should)

| Endpoint | Ai gọi | Request | Response | Lỗi riêng |
|---|---|---|---|---|
| POST /cases/{id}/dossiers | CLERK | `files[]`, `docNames[]` | 201 `{dossierId, recordedAt, createdBy}` | APPEAL_REQUIRED (chưa có kháng cáo hoặc kháng nghị), META_MISMATCH |
| GET /cases/{id}/dossiers | CLERK, JUDGE | không | 200 | |
| POST /dossiers/{id}/checks | CLERK (kể cả Tòa phúc thẩm, đã được thêm vào vụ) | `files[]`, `docNames[]` | 200 `{result: KHỚP / KHÁC BẢN ĐÃ GHI, checkedAt}`; ghi thêm 1 IntegrityCheck | DOSSIER_NOT_FOUND |

## Kiểm tra tệp (tương đương tab "Kiểm tra tệp" của bản Streamlit)

| Endpoint | Ai gọi | Request | Response | Lỗi riêng |
|---|---|---|---|---|
| POST /verify | PUBLIC | `receipt` (file JSON tải từ `GET /receipts/{code}`: `{receipt, signature, anchor}`), `files[]` | 200 `{valid, receiptCode, checks:[{name, ok, detail?}]}`: kiểm chữ ký hệ thống, băm lại file, tính lại Ha, Habc, Bundle, kiểm bản ghi 164 byte từng file (`SHA256(raw) = recordHash`, chứa đúng hash file), kiểm đường dẫn Merkle hai tầng từ recordHash (groupPath, batchPath) tới root đợt, payload ANCH (85 byte) chứa root và đủ số bản ghi để có seq (fromSeq ≤ seq < fromSeq + recordCount), đọc giao dịch trên Sepolia (thành công, Input Data = payload, gửi từ `ANCHOR_WALLET_ADDRESS`). Chưa neo thì `valid = false` | INVALID_RECEIPT_FORMAT, CHAIN_UNAVAILABLE |

## Quản trị (ADMIN)

| Endpoint | Request | Response | Lỗi riêng |
|---|---|---|---|
| POST /admin/users | `{username, email, fullName, role, courtName, password?}` (mọi vai trò) | 201; không gửi `password` thì trả `temporaryPassword` (1 lần) | USERNAME_EXISTS, EMAIL_EXISTS |
| GET /admin/users | `q, role, page` | 200 | |
| PATCH /admin/users/{id} | `{fullName, role, status, courtName, password}` | 200 | USER_NOT_FOUND, INVALID_STATE (tự khóa mình) |
| GET /admin/access-logs | `userId, caseId, result, from, to, page` | 200 (có cả thao tác bị từ chối) | |

## Neo lên Sepolia

Chạy nền, không có API gọi. Thứ được neo là **LogRecord** (bản ghi 164 byte của mọi sự kiện A, E, C, D), theo
**đợt** (`AnchorBatch`): các bản ghi liền nhau `from_seq..to_seq`, cây Merkle hai tầng (nhóm theo người ghi), Input
Data của giao dịch = `payload` ANCH 85 byte. Giao dịch đầu tiên của ví là KEYR. Chi tiết: `docs/entities.md`.
`ANCHOR_MODE` trong `.env`:

- `per_submission` (demo): mỗi vòng worker (`ANCHOR_INTERVAL_SECONDS`) chốt một đợt từ mọi bản ghi chưa neo.
- `daily` (chưa làm): cuối ngày chốt một đợt.

Lần nộp **Đã neo** khi bản ghi của mọi file nằm trong đợt có giao dịch ANCH đã lên khối (CONFIRMED).

Giao dịch kẹt quá `ANCHOR_RETRY_SECONDS` → gửi lại cùng nonce, phí cao hơn (`ChainTx.replaces_tx_id`). Giao dịch
FAILED hoặc ví bị dùng ngoài worker → `AnchorState.halted = true`, job neo dừng tới khi người vận hành xử lý.
