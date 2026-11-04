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
| GET /receipts/{code} | PARTY (của mình) | không | 200 biên nhận JSON có chữ ký hệ thống (có hash để tự kiểm tra); khi ANCHORED có thêm `anchor: {rootHash, merkleProof, txHash, blockNumber, blockTime, explorerUrl}` | RECEIPT_NOT_FOUND |
| GET /signing-key | PUBLIC | không | 200 `{algorithm: "Ed25519", publicKey}` để tự kiểm chữ ký biên nhận | |

`status` suy ra từ bảng `Anchor`/`AnchorLeaf`: `PENDING_ANCHOR` / `ANCHORED` / `ANCHOR_FAILED`.

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

Chỉ đối chiếu được biên nhận đã neo (`REQUIRE_ANCHOR_BEFORE_VERIFY=true`, mặc định).

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
| POST /verify | PUBLIC | `receipt` (file JSON tải từ `GET /receipts/{code}`: `{receipt, signature, anchor}`), `files[]` | 200 `{valid, receiptCode, checks:[{name, ok, detail?}]}`: kiểm chữ ký hệ thống, băm lại file, tính lại Ha, Habc, Bundle, kiểm đường dẫn Merkle tới rootHash, đọc giao dịch trên Sepolia (thành công, Input Data = rootHash, gửi từ `ANCHOR_WALLET_ADDRESS`). Chưa neo thì `valid = false` | INVALID_RECEIPT_FORMAT, CHAIN_UNAVAILABLE |

## Quản trị (ADMIN)

| Endpoint | Request | Response | Lỗi riêng |
|---|---|---|---|
| POST /admin/users | `{username, email, fullName, role, courtName, password?}` (mọi vai trò) | 201; không gửi `password` thì trả `temporaryPassword` (1 lần) | USERNAME_EXISTS, EMAIL_EXISTS |
| GET /admin/users | `q, role, page` | 200 | |
| PATCH /admin/users/{id} | `{fullName, role, status, courtName, password}` | 200 | USER_NOT_FOUND, INVALID_STATE (tự khóa mình) |
| GET /admin/access-logs | `userId, caseId, result, from, to, page` | 200 (có cả thao tác bị từ chối) | |

## Neo lên Sepolia

Chạy nền, không có API gọi. `ANCHOR_MODE` trong `.env`:

- `per_submission` (demo): neo `bundle_hash` ngay sau mỗi lần nộp; `merkleProof = []`, `rootHash = bundle_hash`.
- `daily`: cuối ngày gom `bundle_hash` của mọi lần nộp trong ngày thành cây Merkle, neo 1 gốc.

Neo lỗi → ghi `Anchor` với `result = FAILED`; worker tự thử lại bằng một `Anchor` mới.
