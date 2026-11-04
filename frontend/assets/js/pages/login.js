/* ==========================================================================
   Trang Đăng nhập – pages/auth/login.html
   Đăng nhập qua API POST /auth/login bằng tài khoản có sẵn (backend/scripts/seed.py):
     - duongsu / 1234 → Đương sự
     - thuky   / 5678 → Thư ký tòa án
   Vào trang này = đăng xuất (xóa phiên cũ).
   Xem trước trạng thái: login.html?state=error | ?state=success
   ========================================================================== */

(function (EC) {
  'use strict';

  const REDIRECT_DELAY_MS = 2500;

  EC.auth.clear();

  const form = document.getElementById('login-form');
  const accountInput = document.getElementById('login-account');
  const passwordInput = document.getElementById('login-password');
  const togglePasswordBtn = document.getElementById('toggle-password');
  const attemptsText = document.getElementById('login-attempts');
  const errorText = document.querySelector('#modal-login-error .modal__text');
  const submitButton = form.querySelector('[type="submit"]');

  // ---- Hiện / ẩn mật khẩu ----
  togglePasswordBtn.addEventListener('click', () => {
    const show = passwordInput.type === 'password';
    passwordInput.type = show ? 'text' : 'password';
    togglePasswordBtn.setAttribute('aria-label', show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
    togglePasswordBtn.innerHTML = `<i data-lucide="${show ? 'eye-off' : 'eye'}" class="icon-sm"></i>`;
    EC.refreshIcons();
  });

  // ---- Đăng nhập VNeID: chưa hỗ trợ ----
  document.getElementById('vneid-button').addEventListener('click', () => {
    EC.modal.open('modal-vneid');
  });

  // ---- Gửi form ----
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submitButton) submitButton.disabled = true;
    try {
      showSuccess(await EC.auth.login(accountInput.value.trim(), passwordInput.value));
    } catch (err) {
      showError(err.message);
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });

  /** Thông báo lỗi lấy từ server (sai tài khoản, mất kết nối, vai trò chưa có giao diện) */
  function showError(message = 'Tên đăng nhập hoặc mật khẩu không đúng.') {
    errorText.textContent = message;
    attemptsText.hidden = true; // máy chủ chưa giới hạn số lần thử
    EC.modal.open('modal-login-error');
  }

  function showSuccess(role, { autoRedirect = true } = {}) {
    const name = EC.auth.user()?.fullName || EC.USERS[role].name; // xem trước (?state=success) chưa đăng nhập
    const target = EC.url(EC.HOME_PAGE[role]);
    const pageName = role === 'clerk' ? 'Các lần lưu chứng cứ' : 'Lưu chứng';

    document.getElementById('login-success-text').textContent =
      `Xin chào ${name}. Đang chuyển đến trang ${pageName}…`;
    document.getElementById('login-continue').href = target;
    EC.modal.open('modal-login-success');

    // Thanh tiến trình chạy rồi tự chuyển trang
    const bar = document.getElementById('login-progress');
    if (!autoRedirect) {
      bar.style.width = '60%';
      return;
    }
    const start = performance.now();
    (function tick(now) {
      const ratio = Math.min(1, (now - start) / REDIRECT_DELAY_MS);
      bar.style.width = ratio * 100 + '%';
      if (ratio < 1) requestAnimationFrame(tick);
      else window.location.href = target;
    })(start);
  }

  // ---- Xem trước trạng thái qua URL ----
  const state = EC.param('state');
  if (state === 'error') {
    showError();
  } else if (state === 'success') {
    accountInput.value = 'duongsu';
    showSuccess('litigant', { autoRedirect: false });
  }
})(window.EC);
