# Entity (16 entity)

## Vai trò

- Tài khoản (`User.role`): `PARTY` (đương sự và luật sư), `CLERK` (thư ký, gồm cả thư ký Tòa phúc thẩm), `JUDGE`, `ADMIN`.
- Vai trò trong vụ (`CaseParticipant.role_in_case`): `PLAINTIFF`, `DEFENDANT`, `LAWYER`, `CLERK`, `JUDGE`.
- Người giám định không có tài khoản, Thư ký ghi thay.

## Nguyên tắc chỉ ghi thêm (F6)

Bảng chứa hash, kết quả so và nhật ký **chỉ INSERT**: tài khoản ứng dụng không có quyền `UPDATE`, `DELETE`
(migration `REVOKE UPDATE, DELETE`). Thông tin thay đổi theo thời gian (trạng thái neo, kết quả tính lại) không sửa
dòng cũ mà ghi thêm vào bảng riêng (`AnchorLeaf`, `ChainTx`, `ChainTxResult`, `IntegrityCheck`).

| Chỉ ghi thêm | Được sửa |
|---|---|
| Submission, FileHash, LogRecord, AnchorBatch, AnchorLeaf, ChainTx, ChainTxResult, IntegrityCheck, AppraisalStep, Dossier, DossierItem, AccessLog | User, CourtCase, CaseParticipant, AnchorState (chỉ UPDATE, không thêm / xóa dòng) |

Chưa làm: `OtsStamp` (chỉ cần nếu demo đóng dấu OpenTimestamps).

## USER

Tài khoản có sẵn (seed hoặc admin tạo), không có tự đăng ký. Mọi vai trò đăng nhập bằng `username` + mật khẩu.

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| username | VARCHAR(50) | UQ, NN | Tên đăng nhập, ví dụ `duongsu`, `thuky` |
| email | VARCHAR(255) | UQ, NN | |
| full_name | VARCHAR(150) | NN | |
| role | ENUM(PARTY, CLERK, JUDGE, ADMIN) | NN | |
| court_name | VARCHAR(200) | | Tòa của CLERK, JUDGE |
| password_hash | VARCHAR(255) | NN | scrypt, không lưu mật khẩu thô |
| status | ENUM(ACTIVE, DISABLED) | NN, mặc định ACTIVE | |

## COURTCASE

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| case_number | VARCHAR(60) | UQ, NN | |
| title | VARCHAR(300) | NN | |
| court_name | VARCHAR(200) | NN | |
| status | ENUM(OPEN, APPEAL, CLOSED) | NN, mặc định OPEN | |
| appeal_type | ENUM(KHANG_CAO, KHANG_NGHI) | | Trống nếu chưa có kháng cáo, kháng nghị |
| created_by | UUID | FK → User, NN | |

## CASEPARTICIPANT

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| case_id | UUID | FK → CourtCase, NN | |
| user_id | UUID | FK → User, NN | |
| role_in_case | ENUM(PLAINTIFF, DEFENDANT, LAWYER, CLERK, JUDGE) | NN | |

Duy nhất theo (case_id, user_id, role_in_case).

## SUBMISSION (một lần nộp = một biên nhận = một Bundle)

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| receipt_code | VARCHAR(30) | UQ, NN | Ví dụ TX-0001 |
| type | ENUM(SELF, COURT_LOT) | NN | Đương sự lưu chứng / lô nộp tại Tòa |
| owner_id | UUID | FK → User, NN | Đương sự (SELF) hoặc Thư ký (COURT_LOT) |
| case_id | UUID | FK → CourtCase | Chỉ có với COURT_LOT |
| lot_no | INT | | Thứ tự lô trong vụ; duy nhất theo (case_id, lot_no) |
| place | VARCHAR(200) | | Nơi nộp (COURT_LOT) |
| file_count | INT | NN | |
| submitted_at | TIMESTAMPTZ | NN | Giờ server |
| bundle_scheme | VARCHAR(30) | NN | `per-file-time-v2` (SELF) hoặc `court-lot-v1` (COURT_LOT) |
| habc | CHAR(64) | NN | |
| bundled_at | VARCHAR(40) | NN | Lưu đúng chuỗi đã băm, ví dụ 2026-11-01T23:53:30.56+07:00 |
| bundle_time_hash | CHAR(64) | NN | SHA256(bundled_at) |
| lot_meta_hash | CHAR(64) | | Chỉ COURT_LOT: SHA256(`"{place}\|{file_count}"`) |
| bundle_hash | CHAR(64) | NN | Lá Merkle khi neo |
| signature | TEXT | NN | Chữ ký hệ thống (EIP-191, hex 65 byte) trên 58 byte: nhãn ‖ số khóa ‖ số thứ tự ‖ SHA256(receipt_json) |
| receipt_json | JSONB | NN | Biên nhận tạm, tự chứa, ghi một lần lúc nộp |

Bỏ so với bản trước: `bundle_tx_hash`, `block_number`, `block_time`, `status`, `last_result`, `last_checked_at`
(chuyển sang `ChainTx`, `ChainTxResult`, `IntegrityCheck`).

Trạng thái neo **suy ra** từ bản ghi (`record_seq`) của các file trong lần nộp, không lưu:

- `ANCHORED`: bản ghi của **mọi** file nằm trong một `AnchorBatch` có giao dịch ANCH với `ChainTxResult` CONFIRMED.
- `ANCHOR_FAILED`: có file nằm trong đợt mà giao dịch ANCH bị FAILED (job neo dừng, cần người xử lý).
- `PENDING_ANCHOR`: còn lại (chưa vào đợt, hoặc giao dịch chưa lên khối).

Công thức hash tổng:

- `per-file-time-v2`: `Bundle = SHA256(Habc ‖ SHA256(bundled_at))`.
- `court-lot-v1`: `Bundle = SHA256(Habc ‖ SHA256(bundled_at) ‖ lot_meta_hash)` → đổi file, giờ, nơi nộp hay số lượng đều làm Bundle khác (F3-AC5).

## FILEHASH

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| submission_id | UUID | FK → Submission, NN | |
| position | INT | NN | Thứ tự trong lần nộp; duy nhất theo (submission_id, position) |
| file_name | VARCHAR(255) | NN | Chỉ là tên, không lưu file |
| file_code | VARCHAR(40) | UQ, NN | Ví dụ TX-0001-2 |
| file_hash | CHAR(64) | NN | Hi |
| hashed_at | VARCHAR(40) | NN | Lưu đúng chuỗi đã băm, không dùng kiểu timestamp |
| time_hash | CHAR(64) | NN | Hti |
| leaf_hash | CHAR(64) | NN | Ha |
| sleep_after_seconds | NUMERIC(4,2) | | Thời gian nghỉ sau file này |
| baseline_file_id | UUID | FK → FileHash | Bản lưu chứng (A) để so; trống nếu không có mốc |
| result | ENUM(UNCHANGED, CHANGED, NO_BASELINE) | | Chỉ có với file trong lô tại Tòa, tính lúc nhận |
| checked_at | TIMESTAMPTZ | | Lúc tính `result` (lúc nhận) |
| record_seq | BIGINT | FK → LogRecord, UQ, NN | Bản ghi A (lưu chứng) hoặc E (file trong lô), ghi trong cùng thao tác database |

Kết quả tính lại sau này nằm ở `IntegrityCheck` (target = FILE).

## LOGRECORD (mỗi sự kiện một dòng, đúng 164 byte)

Chỉ ghi thêm. Mỗi bản ghi nối với bản ghi liền trước bằng `prev_record_hash`, và là một lá của cây Merkle khi neo.

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| seq | BIGINT | PK | = seq bản ghi cuối + 1, cấp trong cùng thao tác có khóa; không dùng sequence của PostgreSQL (rollback không để lại lỗ hổng) |
| event_type | SMALLINT | NN, 1–4 | 1 = A (lưu chứng), 2 = E (nộp lô / đối chiếu), 3 = C (giám định), 4 = D (chốt hồ sơ) |
| file_hash | CHAR(64) | NN | Dấu vân tay file (D: hash danh mục) |
| case_id | UUID | FK → CourtCase | Trống với loại A |
| actor_id | UUID | FK → User, NN | Người ghi |
| ts | BIGINT | NN | Số giây Unix, đúng con số trong `raw`; hiển thị theo giờ Việt Nam |
| result | SMALLINT | NN, 0–3 | 0 = loại A, D; 1 = UNCHANGED; 2 = CHANGED; 3 = NO_BASELINE |
| ref_seq | BIGINT | FK → LogRecord | Bản ghi liên quan: E trỏ A, C trỏ E (trống nếu E là NO_BASELINE) |
| prev_record_hash | CHAR(64) | UQ, NN | `record_hash` của bản ghi liền trước; bản ghi đầu = 64 số 0 |
| record_hash | CHAR(64) | UQ, NN | `SHA256(raw)`; lá Merkle = `SHA256(0x00 ‖ record_hash)` |
| raw | BYTEA | NN, CHECK độ dài = 164 | Nguyên 164 byte để đối chiếu và xuất biên nhận |

Bố cục `raw` (big-endian, theo đúng thứ tự cột; code: `backend/app/core/log_record.py`):

| Trường | Byte | Cách ghi |
|---|---|---|
| seq | 8 | uint64 |
| event_type | 2 | uint16 |
| file_hash | 32 | SHA-256 nhị phân |
| case_id | 36 | UUID dạng chữ ASCII; trống = `00000000-0000-0000-0000-000000000000` |
| actor_id | 36 | UUID dạng chữ ASCII |
| ts | 8 | uint64 |
| result | 2 | uint16 |
| ref_seq | 8 | uint64; trống = 0 |
| prev_record_hash | 32 | SHA-256 nhị phân |
| **Tổng** | **164** | |

Sự kiện nào ghi bản ghi nào:

| Thao tác | Loại | file_hash | ref_seq | Dòng nối với bản ghi |
|---|---|---|---|---|
| Đương sự lưu chứng (mỗi file) | A | Hi | — | FileHash |
| Nộp lô tại Tòa (mỗi file) | E | Hi | A của bản lưu chứng (nếu có mã) | FileHash |
| Thư ký đối chiếu file trong biên nhận / tính lại 1 file trong lô | E | hash file vừa chọn | A / E của file đó | IntegrityCheck |
| Tính lại hash tổng lô | E | hash tổng tính lại | — | IntegrityCheck |
| Giám định gửi đi / nhận về | C | hash file lúc đó | E của chứng cứ | AppraisalStep |
| Chốt hồ sơ | D | hash danh mục | — | Dossier |
| Phúc thẩm đối chiếu hồ sơ chốt | E | hash danh mục tính lại | D | IntegrityCheck |

Ghi tuần tự (khóa `pg_advisory_xact_lock`) để 2 thao tác cùng lúc không cùng nối vào một bản ghi liền trước.

## ANCHORBATCH (một đợt neo; thay bảng Anchor)

Ghi một lần lúc chốt đợt, trước khi gửi giao dịch.

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| batch_no | BIGINT | UQ, NN | Số đợt, tăng nghiêm ngặt từ 1, không dùng lại |
| from_seq | BIGINT | FK → LogRecord, NN | Bản ghi đầu của đợt |
| to_seq | BIGINT | FK → LogRecord, NN | Bản ghi cuối; đợt sau có `from_seq = to_seq` đợt trước + 1 |
| prev_root | CHAR(64) | NN | Root đợt trước; đợt 1 toàn số 0 |
| root | CHAR(64) | NN | Root cây Merkle hai tầng của đợt |
| payload | BYTEA | NN | Đúng các byte gửi lên chuỗi (bên dưới); gửi lại khi kẹt |
| nonce | BIGINT | UQ, NN | Cấp từ `AnchorState.next_nonce` trong cùng thao tác database với dòng này |
| created_at | TIMESTAMPTZ | NN | |

Cây hai tầng: bản ghi trong đợt chia nhóm theo người ghi (`actor_id`; nhóm xếp theo bản ghi đầu tiên, lá trong nhóm
xếp theo seq). Lá = `SHA256(0x00 ‖ recordHash)`, nút trong = `SHA256(0x01 ‖ trái ‖ phải)`, tầng lẻ thì nút cuối đẩy
thẳng lên. Mỗi nhóm ra một `subRoot`; tầng trên dựng cây trên các `subRoot` (vào như một nút, không thêm 0x00).

Payload (big-endian; mọi dòng: nhãn 4 byte ‖ phiên bản 1 byte ‖ nội dung). ANCH theo tài liệu kỹ thuật 1027_Tech
(`backend/app/core/payload.py`). KEYR, NOOP cùng quy ước, chưa có trong tài liệu, nhóm cần chốt
(`backend/app/core/anchor_payload.py`):

| Loại | Byte | Nội dung |
|---|---|---|
| ANCH | 85 | `"ANCH"` ‖ version ‖ batch_no u64 ‖ record_count u64 ‖ prev_root 32 ‖ root 32 |
| KEYR | 35 | `"KEYR"` ‖ version ‖ key_no u16 (`RECEIPT_KEY_NO`) ‖ địa chỉ khóa ký biên nhận EIP-191 20 byte ‖ from_seq u64 |
| NOOP | 13 | `"NOOP"` ‖ version ‖ batch_no u64 |

ANCH không ghi from_seq: `from_seq` = `to_seq` đợt trước + 1, `record_count` = `to_seq − from_seq + 1`.

## ANCHORLEAF (mỗi bản ghi là một lá)

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| batch_id | UUID | FK → AnchorBatch, NN | |
| record_seq | BIGINT | FK → LogRecord, UQ, NN | Mỗi bản ghi chỉ thuộc một đợt |
| group_index | INT | NN | Nhóm thứ mấy trong đợt |
| leaf_index | INT | NN | Vị trí lá trong nhóm |
| leaf_hash | CHAR(64) | NN | `SHA256(0x00 ‖ recordHash)` |
| group_path | JSONB | NN | Lá → subRoot: `[{"side": "L" \| "R", "hash": "…"}]` |
| batch_path | JSONB | NN | subRoot → root đợt |

Duy nhất theo (batch_id, group_index, leaf_index). Không thêm `batch_id` vào LogRecord.

## CHAINTX (mọi giao dịch ví neo đã ký)

Ghi **trước** khi phát giao dịch lên mạng, để worker chết giữa chừng vẫn biết `tx_hash` mà theo dõi / thay thế.

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| kind | ENUM(ANCH, KEYR, NOOP) | NN | KEYR là giao dịch đầu tiên của ví |
| batch_id | UUID | FK → AnchorBatch | Có với ANCH, và NOOP hủy một đợt |
| nonce | BIGINT | NN | Giao dịch thay thế dùng lại nonce cũ |
| tx_hash | CHAR(66) | UQ, NN | |
| payload | BYTEA | NN | Dữ liệu đã gửi |
| replaces_tx_id | UUID | FK → ChainTx | Giao dịch bị thay thế (khi kẹt) |
| sent_at | TIMESTAMPTZ | NN | |

## CHAINTXRESULT

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| tx_id | UUID | FK → ChainTx, NN | |
| status | ENUM(CONFIRMED, FINALIZED, FAILED) | NN | Duy nhất theo (tx_id, status) |
| block_number | BIGINT | | |
| block_time | TIMESTAMPTZ | | Mốc thời gian chính thức của đợt |
| observed_at | TIMESTAMPTZ | NN | |

## ANCHORSTATE (một dòng, được sửa)

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | SMALLINT | PK, CHECK = 1 | |
| next_nonce | BIGINT | NN | Nonce kế tiếp sẽ cấp |
| halted | BOOLEAN | NN, mặc định false | true thì job neo dừng |
| halted_reason | TEXT | | |

Worker neo, mỗi vòng:

1. Chưa có ChainTx nào: lấy `next_nonce` = nonce của ví trên mạng. Nonce trên mạng vượt `next_nonce` (ví bị dùng
   ngoài worker): dừng.
2. Theo dõi giao dịch: lên khối thì ghi CONFIRMED hoặc FAILED. FAILED thì dừng job neo. Khối đã chốt thì ghi
   FINALIZED. Kẹt quá `ANCHOR_RETRY_SECONDS` thì gửi lại cùng payload, cùng nonce, phí gấp đôi (`replaces_tx_id`).
3. Chưa có KEYR: gửi KEYR.
4. Chốt đợt từ các bản ghi sau đợt trước, rồi gửi ANCH.

NOOP chưa tự động: hủy một đợt kẹt là thao tác người vận hành.

## INTEGRITYCHECK (mỗi lần tính lại = một dòng)

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| target | ENUM(LOT, FILE, DOSSIER) | NN | |
| submission_id | UUID | FK → Submission | target = LOT |
| file_id | UUID | FK → FileHash | target = FILE |
| dossier_id | UUID | FK → Dossier | target = DOSSIER |
| result | ENUM(UNCHANGED, CHANGED) | NN | |
| phase | VARCHAR(100) | | Giai đoạn tố tụng khi thư ký đối chiếu biên nhận |
| checked_by | UUID | FK → User, NN | |
| checked_at | TIMESTAMPTZ | NN | |
| record_seq | BIGINT | FK → LogRecord, UQ, NN | Bản ghi E |

Đúng một trong `submission_id`, `file_id`, `dossier_id` có giá trị, khớp với `target`.
"Kiểm tra lúc [giờ]" (F5-AC4) = `checked_at` mới nhất, hoặc lúc nhận nếu chưa tính lại.

## APPRAISALSTEP

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| file_id | UUID | FK → FileHash, NN | |
| step | ENUM(SEND, RETURN) | NN | |
| file_hash | CHAR(64) | NN | |
| result | ENUM(UNCHANGED, CHANGED) | NN | So với hash lúc nhận (E) |
| recorded_by | UUID | FK → User, NN | |
| recorded_at | TIMESTAMPTZ | NN | |
| record_seq | BIGINT | FK → LogRecord, UQ, NN | Bản ghi C |

## DOSSIER

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| case_id | UUID | FK → CourtCase, NN | |
| appeal_type | ENUM(KHANG_CAO, KHANG_NGHI) | NN | |
| catalog_hash | CHAR(64) | NN | SHA256 của các dòng `"{position}\|{doc_name}\|{file_hash}"` nối bằng `\n` |
| file_count | INT | NN | |
| created_by | UUID | FK → User, NN | |
| created_at | TIMESTAMPTZ | NN | |
| record_seq | BIGINT | FK → LogRecord, UQ, NN | Bản ghi D |

## DOSSIERITEM

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| dossier_id | UUID | FK → Dossier, NN | |
| position | INT | NN | Duy nhất theo (dossier_id, position) |
| doc_name | VARCHAR(255) | NN | |
| file_hash | CHAR(64) | NN | |

## ACCESSLOG

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | BIGINT | PK, tự tăng | |
| user_id | UUID | FK → User | Trống nếu chưa đăng nhập |
| role | VARCHAR(20) | | Vai trò lúc thao tác |
| action | VARCHAR(60) | NN | |
| resource | VARCHAR(100) | | |
| case_id | UUID | FK → CourtCase | Nếu thuộc một vụ |
| result | ENUM(ALLOW, DENY) | NN | Ghi cả thao tác bị từ chối |
| ip | INET | | |
| created_at | TIMESTAMPTZ | NN | |

## Quan hệ

- User – CaseParticipant – CourtCase: N–M.
- CourtCase 1–N Submission (COURT_LOT).
- User 1–N Submission.
- Submission 1–N FileHash.
- FileHash N–1 FileHash (`baseline_file_id`).
- FileHash 1–N AppraisalStep.
- Submission / FileHash / Dossier 1–N IntegrityCheck.
- CourtCase 1–N Dossier, Dossier 1–N DossierItem.
- User 1–N AccessLog.
- LogRecord N–1 User (`actor_id`), LogRecord N–1 CourtCase (`case_id`, có thể trống), LogRecord N–1 LogRecord (`ref_seq`).
- FileHash, AppraisalStep, Dossier, IntegrityCheck: mỗi dòng 1–1 với một LogRecord (`record_seq`).
- AnchorBatch 1–N AnchorLeaf; AnchorLeaf 1–1 LogRecord (`record_seq`).
- AnchorBatch 1–N ChainTx (ANCH và NOOP); ChainTx N–1 ChainTx (`replaces_tx_id`).
- ChainTx 1–N ChainTxResult (tối đa một dòng cho mỗi status).

## ERD

https://app.diagrams.net/#G1iwhRl9Dt8VGK3WbLJxBedekO4YBJbFIk#%7B%22pageId%22%3A%22ks5T651AsH4NjlYna9_X%22%7D
(ERD cần cập nhật thêm LogRecord, AnchorBatch, AnchorLeaf, ChainTx, ChainTxResult, AnchorState, IntegrityCheck, các
cột `record_seq`, cột User.username và bỏ các cột đã chuyển khỏi Submission.)
