# EvidenceChain – Frontend (HTML / CSS / JS)

Giao diện web tĩnh của EvidenceChain, dựng lại từ bản thiết kế Google Stitch theo cấu trúc chuẩn:
HTML cho từng trang, CSS tách theo lớp (nền tảng → bố cục → component → trang), JavaScript thuần,
**không cần cài đặt hay build**.

## Chạy thử

- Cách nhanh nhất: mở `index.html` bằng trình duyệt (bấm đúp). Trang sẽ tự chuyển tới trang đăng nhập.
- Hoặc dùng extension **Live Server** của VS Code: chuột phải `index.html` → *Open with Live Server*.

Cần có mạng để tải font Google và bộ icon Lucide (từ CDN).

**Tài khoản demo:**

| Tài khoản | Mật khẩu | Vai trò       | Vào trang            |
|-----------|----------|---------------|----------------------|
| `duongsu` | `1234`   | Đương sự      | Lưu chứng cứ         |
| `thuky`   | `5678`   | Thư ký tòa án | Các lần lưu chứng cứ |

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
│       │   └── mock-data.js      ← dữ liệu mẫu (chỗ để nối API backend sau này)
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

- **Dữ liệu được thống nhất** giữa các màn hình. Bản Stitch có chỗ mâu thuẫn, ví dụ TX-0007 lúc là "Đã ghi nhận", lúc là "Đã khóa".
  Ở đây TX-0007 là "Đã khóa"; trạng thái "chưa khóa" xem ở `receipt-detail.html?id=TX-0010`.
- Sửa lỗi của bản Stitch: trang Đương sự bị mất tiêu đề cột và mất một hàng; mục menu không có chữ; biên nhận TX-0003 thiếu nhãn "Người lưu".
- Trang **Lưu chứng cứ** tính **SHA-256 thật** ngay trên trình duyệt cho file bạn chọn, rồi lưu biên nhận mới vào `localStorage`.
  Trang **Đối chiếu** so mã băm thật với các biên nhận này. Với dữ liệu mẫu (không có mã băm) thì tạm so theo tên file.
  Muốn xóa các biên nhận đã tạo thử, gõ trong Console: `EC.data.resetSavedReceipts()`.
- **Tự khóa lúc 23:59**: lần lưu chứng cứ "Đã ghi nhận" tự chuyển "Đã khóa" khi qua 23:59 ngày ghi nhận
  (so với giờ thật của máy). Muốn test ngay không chờ: thêm `?lock=TX-0012` vào cuối URL của trang bất kỳ
  (vd `pages/clerk/submissions.html?lock=TX-0012`), hoặc gõ trong Console: `EC.data.lockNow('TX-0012')` rồi F5.

## Nối backend sau này

Mọi trang chỉ đọc dữ liệu qua `EC.data` trong `assets/js/data/mock-data.js`.
Khi có API (từ `receipt.py` / `chain.py`), chỉ cần thay phần dữ liệu mẫu trong file đó bằng lời gọi `fetch(...)`.
