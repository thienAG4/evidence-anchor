# Entity (12 entity)

## Vai trò

- Tài khoản (`User.role`): `PARTY` (đương sự và luật sư), `CLERK` (thư ký, gồm cả thư ký Tòa phúc thẩm), `JUDGE`, `ADMIN`.
- Vai trò trong vụ (`CaseParticipant.role_in_case`): `PLAINTIFF`, `DEFENDANT`, `LAWYER`, `CLERK`, `JUDGE`.
- Người giám định không có tài khoản, Thư ký ghi thay.

## Nguyên tắc chỉ ghi thêm (F6)

Bảng chứa hash, kết quả so và nhật ký **chỉ INSERT**: tài khoản ứng dụng không có quyền `UPDATE`, `DELETE`
(migration `REVOKE UPDATE, DELETE`). Thông tin thay đổi theo thời gian (trạng thái neo, kết quả tính lại) không sửa
dòng cũ mà ghi thêm vào bảng riêng (`Anchor`, `AnchorLeaf`, `IntegrityCheck`).

| Chỉ ghi thêm | Được sửa |
|---|---|
| Submission, FileHash, Anchor, AnchorFinality, AnchorLeaf, IntegrityCheck, AppraisalStep, Dossier, DossierItem, AccessLog | User, CourtCase, CaseParticipant |

## USER

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
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
(chuyển sang `Anchor`, `AnchorLeaf`, `IntegrityCheck`).

Trạng thái neo **suy ra**, không lưu:

- `ANCHORED` (hoàn chỉnh): có `AnchorLeaf` thuộc một `Anchor` có `result = CONFIRMED` **và** đã có `AnchorFinality`
  (block chứa giao dịch đã chốt). Chỉ lúc này biên nhận mới có phần `anchor` và thư ký mới đối chiếu được.
- `ANCHORED_UNFINALIZED` ("Đã neo, chờ chốt"): có `Anchor` CONFIRMED nhưng block chưa chốt (khoảng 13 phút).
- `ANCHOR_FAILED`: có `AnchorLeaf` nhưng mọi `Anchor` chứa nó đều `FAILED` (worker sẽ thử lại).
- `PENDING_ANCHOR`: chưa có `AnchorLeaf`.

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

Kết quả tính lại sau này nằm ở `IntegrityCheck` (target = FILE).

## ANCHOR (mỗi lần gửi một giao dịch neo)

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| mode | ENUM(PER_SUBMISSION, DAILY) | NN | Demo: PER_SUBMISSION; triển khai: DAILY |
| period_date | DATE | | Ngày được gom (DAILY) |
| root_hash | CHAR(64) | NN | Gốc Merkle; PER_SUBMISSION thì bằng bundle_hash |
| leaf_count | INT | NN | |
| result | ENUM(CONFIRMED, FAILED) | NN | Ghi sau khi biết kết quả giao dịch |
| tx_hash | CHAR(66) | | Có khi đã gửi được giao dịch |
| block_number | BIGINT | | |
| block_time | TIMESTAMPTZ | | |
| error | TEXT | | Lý do FAILED |
| created_at | TIMESTAMPTZ | NN | |

Thử lại sau lỗi = một `Anchor` mới, `Anchor` cũ giữ nguyên.

## ANCHORLEAF

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| anchor_id | UUID | FK → Anchor, NN | |
| submission_id | UUID | FK → Submission, NN | |
| leaf_index | INT | NN | |
| merkle_proof | JSONB | NN | `[{"side": "L" \| "R", "hash": "…"}]`; PER_SUBMISSION thì `[]` |

Duy nhất theo (anchor_id, submission_id).

## ANCHORFINALITY (block chứa giao dịch neo đã chốt)

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| anchor_id | UUID | FK → Anchor, UQ, NN | Mỗi lần neo tối đa 1 dòng |
| tx_block_number | BIGINT | NN | Block thật chứa giao dịch lúc chốt (đọc lại từ chuỗi; khác `Anchor.block_number` nếu block bị xếp lại) |
| finalized_block_number | BIGINT | NN | Block chốt mới nhất lúc worker kiểm |
| created_at | TIMESTAMPTZ | NN | |

Worker ghi khi giao dịch còn, thành công, và `tx_block_number <= finalized_block_number`. Không sửa `Anchor`.

## INTEGRITYCHECK (mỗi lần tính lại = một dòng)

| Attribute | Kiểu | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | |
| target | ENUM(LOT, FILE, DOSSIER) | NN | |
| submission_id | UUID | FK → Submission | target = LOT |
| file_id | UUID | FK → FileHash | target = FILE |
| dossier_id | UUID | FK → Dossier | target = DOSSIER |
| result | ENUM(UNCHANGED, CHANGED) | NN | |
| checked_by | UUID | FK → User, NN | |
| checked_at | TIMESTAMPTZ | NN | |

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
- Anchor 1–N AnchorLeaf, Submission 1–N AnchorLeaf (mỗi lần thử neo một dòng).
- Anchor 1–0..1 AnchorFinality.
- Submission / FileHash / Dossier 1–N IntegrityCheck.
- CourtCase 1–N Dossier, Dossier 1–N DossierItem.
- User 1–N AccessLog.

## ERD

https://app.diagrams.net/#G1iwhRl9Dt8VGK3WbLJxBedekO4YBJbFIk#%7B%22pageId%22%3A%22ks5T651AsH4NjlYna9_X%22%7D
(ERD cần cập nhật thêm Anchor, AnchorLeaf, IntegrityCheck, cột User.username và bỏ các cột đã chuyển khỏi Submission.)
