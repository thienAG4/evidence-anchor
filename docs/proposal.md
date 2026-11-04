# EvidenceChain — Đề xuất tính năng

## Tổng quan

| | |
|---|---|
| **Mục tiêu** | Chỉ trả lời: chứng cứ có ĐÚNG, ĐỦ và KHÔNG BỊ SỬA hay không. Đúng/sai nội dung và việc so sánh chứng cứ là của luật sư, Tòa. |
| **Luồng chính** | Up file (tùy chọn) → Nộp chứng cứ tại Tòa (USB, đưa trực tiếp; thư ký nạp vào hệ thống) → hệ thống tự so hash → (giám định) → phiên họp/xét xử chỉ công bố KẾT QUẢ. |
| **Hash** | Người dùng không thấy, không cần quan tâm số hash. Chỉ thấy kết quả: KHỚP BẢN LƯU CHỨNG / KHÁC BẢN LƯU CHỨNG / KHÔNG CÓ MỐC ĐỂ SO (lô và giám định: KHỚP BẢN ĐÃ GHI / KHÁC BẢN ĐÃ GHI). Chỉ so khớp, không kiểm tra thật/giả. |
| **Blockchain dùng để** | Lưu hash + giờ + ai ghi, chỉ ghi thêm; mỗi ngày neo 1 mã (gốc Merkle) lên chuỗi công khai để không ai lùi ngày hay sửa lén. Không lưu file, không smart contract. **Bản demo:** neo sau mỗi lần nộp (`ANCHOR_MODE=per_submission`). |
| **Ngoài phạm vi** | Hình sự; đánh giá thật/giả hay so sánh nội dung chứng cứ; nội dung kết luận giám định; nộp đơn/chứng cứ trực tuyến từ app lên Tòa (hiện VN chưa có). |

## F1. Up file lưu chứng (tùy chọn) — Đương sự

**Người dùng:** Đương sự chọn file trong app, bấm "Lưu chứng", nhận biên nhận (mã, giờ). Làm trước khi kiện; không làm vẫn kiện bình thường.

**Hệ thống:** Server băm file theo luồng ngay khi nhận rồi bỏ file (không ghi ra đĩa, không lưu DB); giờ do server cấp.
Tòa chỉ nhận biên nhận + hash. Chủ tài khoản đưa lại file là hệ thống tự tìm ra bản ghi của chính họ, không cần nhập mã;
người khác không tra cứu bằng file.

- AC1. Chỉ lưu hash, không lưu file.
- AC2. Giờ do server cấp.
- AC3. Có biên nhận (mã, giờ).
- AC4. Chủ tài khoản đưa lại file thì hệ thống tự tìm ra bản ghi mình đã lưu chứng (giờ, người lưu), không cần nhập mã. Chỉ chủ tài khoản tra cứu bằng file; Tòa và tài khoản khác không tra cứu bằng file (vì ai có file giống hệt cũng biết file được lưu chứng khi nào). Đưa file khác thì không tìm ra.
- AC5. Sau khi neo (cuối ngày; bản demo: ngay sau khi nộp), biên nhận chuyển từ "chờ neo" sang "đã neo" và có đủ dữ liệu để đương sự tự kiểm tra mà không cần hỏi Tòa (mã neo, đường dẫn chứng minh); đương sự tải, lưu được biên nhận hoàn chỉnh.

## F2. Nộp chứng cứ + khởi kiện tại Tòa — Đương sự (nộp tại Tòa); Thư ký (chọn file để đối chiếu)

**Người dùng:** Đương sự nộp đơn kèm chứng cứ trực tiếp tại Tòa (USB, đưa trực tiếp), không qua app vì nộp khởi kiện
buộc gửi Tòa và hiện chưa có đường nộp trực tuyến. Thư ký nhận file và nạp vào hệ thống — nạp ở đây không lưu file, chỉ để đối chiếu hash.

**Hệ thống:** Tự hash file ngay lúc thư ký nạp (thư ký không nhập tay hash) rồi chuyển sang F3. Ghi ngày, giờ, nơi nộp (Tòa nhận hồ sơ).

- AC1. Thư ký nạp file, hệ thống tự tính hash tại chỗ.
- AC2. Ngày, giờ, nơi nộp do hệ thống ghi.
- AC3. Nộp nhiều file trong 1 lần được gom thành 1 lô.
- AC4. App không có chức năng nộp đơn hay chứng cứ lên Tòa.

## F3. Hệ thống tự so hash khi nộp — Hệ thống (tự chạy)

**Người dùng:** Không có thao tác; chỉ thấy kết quả sau khi nộp.

**Hệ thống:**
(a) So từng file với bản đã lưu chứng (A) do thư ký chọn.
(b) Tạo thêm 1 hash tổng của lô (ngày, giờ, nơi nộp, số lượng, danh sách hash từng file). Ví dụ nộp 3 chứng cứ ra 4 hash.
(c) DB lưu giá trị gốc (UNCHANGED / CHANGED / NO_BASELINE); giao diện đổi nhãn qua bảng ánh xạ: file = KHỚP / KHÁC BẢN LƯU CHỨNG; lô và giám định = KHỚP / KHÁC BẢN ĐÃ GHI.

- AC1. File giống bản đã lưu chứng: KHỚP BẢN LƯU CHỨNG.
- AC2. File khác bản đã lưu chứng: KHÁC BẢN LƯU CHỨNG. Không kết luận có người sửa (nén hay chuyển mã cũng ra kết quả này).
- AC3. File chưa từng lưu chứng: KHÔNG CÓ MỐC ĐỂ SO, hash lúc nhận làm mốc.
- AC4. Các file nộp trong cùng 1 lần được gom thành 1 lô, mỗi lô có 1 hash tổng. Ví dụ nộp 3 file ghi 4 hash (3 file + 1 tổng).
- AC5. Về sau tính lại hash tổng từ: file thư ký chọn lại trong hồ sơ Tòa, cùng ngày, giờ, nơi nộp, số lượng đọc từ bản ghi lô trong hệ thống; so với hash tổng đã ghi lúc nhận lô. Thêm, bớt, đổi file hay đổi giờ/nơi/số lượng = KHÁC BẢN ĐÃ GHI, ngược lại KHỚP BẢN ĐÃ GHI.
- AC6. Nộp bổ sung tạo lô mới trong cùng vụ, đánh số thứ tự sau lô cũ, có hash tổng riêng. Lô cũ không bị sửa, hash tổng lô cũ giữ nguyên.
- AC7. Kết quả do hệ thống tính, không nhập tay. Thư ký vẫn chọn bản ghi A để so.

## F4. Giám định: so hash khi file đi, nhận, về — Thư ký (ghi cho GĐV)

**Người dùng:** Thư ký bàn giao file cho người giám định và ghi bước gửi đi; khi file trả về thì ghi bước nhận về.
Người giám định không dùng hệ thống, thư ký ghi thay.

**Hệ thống:** Mỗi bước (đi, về) thư ký chọn file, hệ thống hash lại và so với hash đã ghi lúc nhận file (bản ghi E),
không so với hash lúc lưu chứng (A). Lý do: file KHÁC BẢN LƯU CHỨNG vẫn được nhận và giám định trên bản đang giữ.
Việc bàn giao cho người giám định có biên bản giấy ngoài hệ thống.

- AC1. Chỉ gửi đi khi file vẫn giống hash đã ghi lúc nhận ở F3 (E), không phải hash lúc lưu chứng (A).
- AC2. File nhận về mà khác hash E: KHÁC BẢN ĐÃ GHI.
- AC3. Thư ký ghi thay mọi bước (gửi đi, nhận về) kèm ngày, giờ; người giám định không có tài khoản trong hệ thống.

## F5. Xem kết quả (phiên họp, xét xử) — Thẩm phán, đương sự, luật sư (xem)

**Người dùng:** Xem 1 dòng kết quả cho từng chứng cứ và cho cả lô.

**Hệ thống:** Chỉ công bố kết quả cuối cùng kèm thời điểm kiểm tra ("Kiểm tra lúc [giờ]"), không công bố mã hash. Luôn kèm chú thích cố định.

- AC1. Mỗi chứng cứ hiện KHỚP BẢN LƯU CHỨNG / KHÁC BẢN LƯU CHỨNG / KHÔNG CÓ MỐC ĐỂ SO; cả lô hiện KHỚP BẢN ĐÃ GHI / KHÁC BẢN ĐÃ GHI; kèm ngày, giờ, nơi nộp, số lượng.
- AC2. Không màn hình, biên bản nào hiện mã hash.
- AC3. Mọi màn hình hiện kết quả có dòng chú thích cố định: "Chỉ so với bản đã lưu, không xác định thật giả."
- AC4. Mỗi kết quả (từng chứng cứ và cả lô) kèm "Kiểm tra lúc [giờ]": giờ hệ thống tính kết quả đó (lúc nhận hoặc lúc tính lại gần nhất).

## F6. Nhật ký không sửa được (chạy ngầm) — Hệ thống

**Người dùng:** Không thấy tính năng này.

**Hệ thống:** Hash chỉ ghi thêm, không sửa/xóa. Thông tin thay đổi theo thời gian (trạng thái neo, kết quả tính lại) được ghi thêm vào bảng riêng, không sửa dòng cũ.

- AC1. Không sửa/xóa được bản ghi cũ.
- AC2. Sửa dữ liệu thì mã neo công khai lệch, phát hiện được.
- AC3. Chuỗi chỉ chứa mã neo, không có file.

## F7. Gắn chứng cứ và bản lưu chứng với vụ án — Thư ký; đương sự (ghi mã vào danh mục)

**Người dùng:** Thư ký chọn vụ án khi tiếp nhận lô, rồi nhập mã biên nhận cho từng file đã lưu chứng. Đương sự ghi mã biên nhận vào danh mục tài liệu kèm đơn.

**Hệ thống:** Gắn lô chứng cứ vào vụ án; gắn bản ghi lưu chứng (A) vào file tương ứng để F3 so. Thư ký thấy giờ lưu chứng và người lưu, không thấy file.

- AC1. Mỗi lô chứng cứ thuộc đúng 1 vụ án do thư ký chọn lúc tiếp nhận.
- AC2. Thư ký nhập mã biên nhận cho file đã lưu chứng; hệ thống gắn bản ghi A vào file đó để so (F3). Mã không tồn tại thì báo lỗi, không so.
- AC3. File không có mã được coi là chưa lưu chứng: KHÔNG CÓ MỐC ĐỂ SO.

## F8. Đăng nhập, phân quyền, nhật ký truy cập — Tất cả vai trò

**Người dùng:** Đăng nhập, rồi chỉ thấy và làm các chức năng của vai trò mình, trong vụ mình tham gia.

**Hệ thống:** Xác thực người dùng, kiểm soát quyền theo vai trò và theo vụ, ghi lại mọi truy cập.

- AC1. Phải đăng nhập mới dùng được; sai thông tin thì bị từ chối.
- AC2. Mỗi vai trò chỉ thấy và làm đúng chức năng của mình: đương sự (F1, xem kết quả vụ mình), thư ký (F2, F3, F4, F7, F9).
- AC3. Người dùng chỉ truy cập vụ án mình tham gia; người ngoài vụ không thấy gì.
- AC4. Nhật ký truy cập ghi ai, làm gì, vào vụ nào, lúc nào (kể cả thao tác bị từ chối); người dùng nghiệp vụ không sửa, xóa được.

## F9. Chốt hồ sơ khi kháng cáo — Thư ký (Tòa sơ thẩm và Tòa phúc thẩm)

**Người dùng:** Khi có kháng cáo hoặc kháng nghị, thư ký chọn lại danh mục và từng file trong hồ sơ rồi bấm "Chốt hồ sơ". Tòa phúc thẩm nhận hồ sơ thì thư ký chọn lại file để đối chiếu.

**Hệ thống:** Hash danh mục và từng file, ghi bản ghi chốt (D) khi hồ sơ rời Tòa; khi phúc thẩm đối chiếu thì so với D.

- AC1. Chỉ chốt được khi có kháng cáo hoặc kháng nghị.
- AC2. Bản ghi chốt gồm hash danh mục và từng file, kèm ngày, giờ, người chốt.
- AC3. Phúc thẩm đối chiếu: nguyên vẹn = KHỚP BẢN ĐÃ GHI; thêm, bớt, sửa file hoặc đổi danh mục = KHÁC BẢN ĐÃ GHI.
