# EvidenceChain – Frontend (HTML / CSS / JS)

Giao diện web tĩnh của EvidenceChain, dựng lại từ bản thiết kế Google Stitch theo cấu trúc chuẩn:
HTML cho từng trang, CSS tách theo lớp (nền tảng → bố cục → component → trang), JavaScript thuần,
**không cần cài đặt hay build**.

## Chạy thử

Giao diện gọi API backend thật (FastAPI + PostgreSQL), nên cần chạy backend trước — xem README ở thư mục gốc, mục 5.1.

- **Cách khuyên dùng:** chạy backend rồi mở **http://localhost:8000** — backend phục vụ luôn thư mục `frontend/`,
  giao diện và API cùng một địa chỉ.
- Hoặc **Live Server** (cổng 5500) / bấm đúp `index.html`: giao diện tự gọi API ở `http://localhost:8000`
  (backend đã mở CORS cho `localhost:5500` và `file://`). Đổi địa chỉ API: đặt `window.EC_API_BASE` trước khi nạp `api.js`.

Cần có mạng để tải font Google và bộ icon Lucide (từ CDN).

**Tài khoản có sẵn** (tạo bằng `backend/scripts/seed.py`):

| Tài khoản | Mật khẩu | Vai trò       | Vào trang            |
|-----------|----------|---------------|----------------------|
| `duongsu` | `1234`   | Đương sự      | Lưu chứng cứ         |
| `thuky`   | `5678`   | Thư ký tòa án | Các lần lưu chứng cứ |

Thẩm phán, admin chưa có giao diện web (đăng nhập sẽ báo), dùng API ở http://localhost:8000/docs.

## Cấu trúc thư mục

```
frontend/
├── index.html                    ← điểm vào, chuyển tới trang đăng nhập
├── app.py                        ← giao diện Streamlit cũ (không liên quan, giữ nguyên)
├── pages/
│   ├── auth/
│   │   └── login.html            ← Đăng nhập
│   ├── litigant/                 ← Vai trò ĐƯƠNG SỰ
│   │   ├── submit-evidence.html  ← Lưu chứng cứ + danh sách biên nhận của tôi
│   │   └── receipt-detail.html   ← Chi tiết biên nhận (?id=TX-0007)
│   └── clerk/                    ← Vai trò THƯ KÝ TÒA ÁN
│       ├── submissions.html      ← Các lần lưu chứng cứ + drawer xem nhanh
│       ├── verify-evidence.html  ← Đối chiếu chứng cứ
│       └── litigants.html        ← Danh sách đương sự
├── assets/
│   ├── images/
│   │   ├── logo.png
│   │   ├── header-banner.png     ← nền header
│   │   └── sidebar-artwork.png   ← tranh minh họa cuối sidebar
│   ├── css/
│   │   ├── main.css              ← nhúng trên MỌI trang, @import các file bên dưới
│   │   ├── base/                 ← variables (màu, font, kích thước), reset, typography
│   │   ├── layout/               ← app-shell, header, sidebar, footer
│   │   ├── components/           ← button, badge, card, form, table, alert,
│   │   │                            stepper (+timeline), modal, drawer
│   │   └── pages/                ← CSS riêng của từng trang (cùng tên với file HTML)
│   └── js/
│       ├── core/
│       │   ├── app.js            ← namespace EC + tiện ích (đường dẫn, escape, SHA-256…)
│       │   └── ui.js             ← mở/đóng Modal & Drawer
│       ├── config/
│       │   ├── navigation.js     ← người dùng mẫu + menu sidebar theo vai trò
│       │   └── status.js         ← bảng trạng thái + hàm EC.badge()
│       ├── data/
│       │   └── api.js            ← gọi API backend, đăng nhập, EC.data (thay mock-data.js)
│       ├── components/           ← <app-header>, <app-sidebar>, <app-footer>
│       └── pages/                ← JS riêng của từng trang (cùng tên với file HTML)
└── design/
    └── stitch-export/            ← bản xuất gốc từ Stitch, CHỈ ĐỂ THAM CHIẾU, không sửa
```

Quy ước đặt tên: tên file và thư mục viết thường, nối bằng gạch ngang (kebab-case), bằng tiếng Anh.
Mỗi trang `pages/<vai-trò>/<tên>.html` có CSS `assets/css/pages/<tên>.css` và JS `assets/js/pages/<tên>.js` cùng tên.

## Component dùng chung (kế thừa)

Header, sidebar, footer viết **một lần** dưới dạng Web Component, trang nào cũng chỉ cần một thẻ:

```html
<app-header role="clerk"></app-header>          <!-- bỏ role → header công khai (trang đăng nhập) -->
<div class="app-body">
  <app-sidebar role="clerk" active="verify"></app-sidebar>
  <main class="app-main">…nội dung trang…</main>
</div>
<app-footer></app-footer>
```

- Đổi tên người dùng / thêm mục menu: sửa `assets/js/config/navigation.js`.
- Đổi màu / font / kích thước toàn hệ thống: sửa `assets/css/base/variables.css`.
- Badge trạng thái: luôn tạo bằng `EC.badge('locked')` để icon, chữ và màu đi cùng nhau.
- Modal / Drawer: `EC.modal.open('id')`, `EC.drawer.open('id')`; nút có `data-close` sẽ tự đóng.

Các script dùng `<script defer>` thường, không dùng ES module, nên vẫn chạy khi mở file trực tiếp (`file://`).

## Bảng đối chiếu với bản Stitch

Các màn hình chỉ khác nhau ở **trạng thái** (lỗi / thành công / modal…) được gộp vào cùng một trang.
Muốn xem lại đúng trạng thái trong ảnh thiết kế thì thêm tham số `?state=` vào URL.

| Thư mục Stitch (tên mất dấu)                         | Ý nghĩa                         | Trang mới                                        |
|------------------------------------------------------|---------------------------------|--------------------------------------------------|
| `ng_nh_p_evidencechain`                              | Đăng nhập                       | `pages/auth/login.html`                          |
| `ng_nh_p_kh_ng_th_nh_c_ng_evidencechain`             | Đăng nhập không thành công      | `pages/auth/login.html?state=error`              |
| `ng_nh_p_th_nh_c_ng_evidencechain`                   | Đăng nhập thành công            | `pages/auth/login.html?state=success`            |
| `l_u_ch_ng_evidencechain`                            | Lưu chứng                       | `pages/litigant/submit-evidence.html`            |
| `l_u_ch_ng_c_th_nh_c_ng_evidencechain`               | Lưu chứng cứ thành công         | `pages/litigant/submit-evidence.html?state=success` |
| `l_u_ch_ng_c_kh_ng_th_nh_c_ng_evidencechain`         | Lưu chứng cứ không thành công   | `pages/litigant/submit-evidence.html?state=error` |
| `chi_ti_t_l_n_l_u_ch_ng_tx_0003_evidencechain`       | Chi tiết lần lưu chứng TX-0003  | `pages/litigant/receipt-detail.html?id=TX-0003`  |
| `chi_ti_t_l_n_l_u_ch_ng_tx_0007_evidencechain`       | Chi tiết lần lưu chứng TX-0007  | `pages/litigant/receipt-detail.html?id=TX-0007`  |
| `c_c_l_n_l_u_ch_ng_evidencechain`                    | Các lần lưu chứng (thư ký)      | `pages/clerk/submissions.html`                   |
| `chi_ti_t_l_n_l_u_ch_ng_c_tx_0007_evidencechain`     | Chi tiết lần lưu chứng cứ (drawer) | `pages/clerk/submissions.html?open=TX-0007`   |
| `i_chi_u_ch_ng_c_evidencechain`                      | Đối chiếu chứng cứ              | `pages/clerk/verify-evidence.html`               |
| `i_chi_u_ch_ng_c_k_t_qu_i_chi_u_evidencechain`       | Đối chiếu – Kết quả đối chiếu   | `pages/clerk/verify-evidence.html?state=result`  |
| `i_chi_u_ch_ng_c_x_c_nh_n_l_u_k_t_qu_evidencechain`  | Đối chiếu – Xác nhận lưu kết quả | `pages/clerk/verify-evidence.html?state=confirm` |
| `i_chi_u_ch_ng_c_l_u_k_t_qu_ki_m_tra_evidencechain`  | Đối chiếu – Đã lưu kết quả kiểm tra | `pages/clerk/verify-evidence.html?state=saved` |
| `ng_s_evidencechain`                                 | Đương sự                        | `pages/clerk/litigants.html`                     |
| `image.png_1`                                        | Ảnh nền header                  | `assets/images/header-banner.png`                |
| `image.png_2`                                        | Logo                            | `assets/images/logo.png`                         |
| `image.png_3`                                        | Tranh minh họa sidebar          | `assets/images/sidebar-artwork.png`              |
| `evidencechain_civil_judicial_system/DESIGN.md`      | Design system                   | `assets/css/base/variables.css`                  |

## Những chỗ khác bản Stitch

- Sửa lỗi của bản Stitch: trang Đương sự bị mất tiêu đề cột và mất một hàng; mục menu không có chữ; biên nhận TX-0003 thiếu nhãn "Người lưu".
- Trang Đương sự hiện **Tên đăng nhập / Email** thay cho Số CCCD / Số điện thoại (hệ thống chưa lưu hai thông tin này).

## Nối với backend

Mọi trang đọc dữ liệu qua `EC.data` trong `assets/js/data/api.js`; trang vẽ trong `EC.data.whenReady(() => …)`.

| Màn hình | API |
|---|---|
| Đăng nhập | `POST /auth/login` → token lưu ở `localStorage`; vào trang đăng nhập = đăng xuất |
| Lưu chứng cứ | `POST /submissions` (gửi file, **máy chủ băm rồi bỏ file**, không lưu file); chỉ nhận PDF, ảnh, video, âm thanh |
| Biên nhận của tôi, chi tiết | `GET /submissions`, `GET /receipts/{mã}`; nút **Tải biên nhận (.json)** = biên nhận + chữ ký + bằng chứng neo |
| Kiểm tra biên nhận (`pages/public/verify-receipt.html`, **không cần đăng nhập**, link ở trang đăng nhập) | `POST /verify`: biên nhận .json + file gốc → từng bước Đạt / Không đạt |
| Các lần lưu chứng cứ (thư ký) | `GET /clerk/receipts` — chỉ đương sự trong **vụ án mà thư ký phụ trách** |
| Đối chiếu | chọn file: `POST /clerk/receipts/{mã}/compare` (xem trước, không ghi); "Lưu kết quả": `POST …/verifications` (máy chủ băm lại, ghi kèm giai đoạn) |
| Đương sự (thư ký) | `GET /clerk/litigants` |

Trạng thái biên nhận: **Đã ghi nhận** = chưa neo lên blockchain → **Đã khóa** = đã neo (không ai sửa được) →
**Tòa đã kiểm tra** = thư ký đã lưu kết quả đối chiếu **đủ n/n file** (đối chiếu dở dang: các file còn lại hiện
"Đang kiểm tra"). Mỗi file chỉ đối chiếu 1 lần; giai đoạn đối chiếu khóa theo lần lưu đầu. Chỉ đối chiếu được sau khi đã khóa, nên muốn thử trang
Đối chiếu phải chạy worker neo (cần `PRIVATE_KEY` ví test có Sepolia ETH — README gốc, mục 5.1).
