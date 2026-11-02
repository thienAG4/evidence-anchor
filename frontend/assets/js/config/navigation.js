/* ==========================================================================
   navigation.js – người dùng mẫu và menu sidebar theo vai trò.
   Thêm trang mới: khai báo thêm một mục trong EC.NAVIGATION[vai trò].
   ========================================================================== */

(function (EC) {
  'use strict';

  /** Người dùng đang đăng nhập (dữ liệu mẫu, chờ nối backend) */
  EC.USERS = {
    litigant: { name: 'Nguyễn Thu Minh', roleLabel: 'Đương sự' },
    clerk: { name: 'Đỗ Thanh Bạch', roleLabel: 'Thư ký tòa án' },
  };

  /** Trang chủ của từng vai trò sau khi đăng nhập */
  EC.HOME_PAGE = {
    litigant: 'pages/litigant/submit-evidence.html',
    clerk: 'pages/clerk/submissions.html',
  };

  EC.LOGIN_PAGE = 'pages/auth/login.html';

  /** Menu sidebar. `key` khớp với thuộc tính active="…" của <app-sidebar>. */
  EC.NAVIGATION = {
    litigant: [
      { key: 'submit', label: 'Lưu chứng cứ mới', icon: 'file-plus', href: 'pages/litigant/submit-evidence.html' },
      { key: 'receipts', label: 'Biên nhận của tôi', icon: 'receipt-text', href: 'pages/litigant/submit-evidence.html#receipt-history' },
    ],
    clerk: [
      { key: 'submissions', label: 'Lần lưu chứng cứ', icon: 'file-text', href: 'pages/clerk/submissions.html' },
      { key: 'litigants', label: 'Đương sự', icon: 'users', href: 'pages/clerk/litigants.html' },
    ],
  };
})(window.EC);
