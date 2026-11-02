/* ==========================================================================
   Trang Đăng nhập – pages/auth/login.html
   Tài khoản demo:
     - duongsu / 1234 → Đương sự  (Nguyễn Thu Minh)
     - thuky   / 5678 → Thư ký tòa án (Đỗ Thanh Bạch)
   Xem trước trạng thái: login.html?state=error | ?state=success
   ========================================================================== */

(function (EC) {
  'use strict';

  // Tài khoản demo — chỉ để trình bày giao diện, thay bằng API đăng nhập khi có backend
  const DEMO_ACCOUNTS = {
    duongsu: { password: '1234', role: 'litigant' },
    thuky: { password: '5678', role: 'clerk' },
  };
  const MAX_ATTEMPTS = 5;
  const REDIRECT_DELAY_MS = 2500;

  const form = document.getElementById('login-form');
  const accountInput = document.getElementById('login-account');
  const passwordInput = document.getElementById('login-password');
  const togglePasswordBtn = document.getElementById('toggle-password');
  const attemptsText = document.getElementById('login-attempts');

  let attemptsLeft = MAX_ATTEMPTS;

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
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const account = DEMO_ACCOUNTS[accountInput.value.trim().toLowerCase()];

    if (account && passwordInput.value === account.password) {
      showSuccess(account.role);
    } else {
      showError();
    }
  });

  function showError() {
    attemptsLeft = Math.max(0, attemptsLeft - 1);
    attemptsText.textContent = attemptsLeft > 0
      ? `Còn ${attemptsLeft} lần thử trước khi tài khoản bị tạm khóa 15 phút.`
      : 'Tài khoản đã bị tạm khóa 15 phút. Vui lòng thử lại sau.';
    EC.modal.open('modal-login-error');
  }

  function showSuccess(role, { autoRedirect = true } = {}) {
    const user = EC.USERS[role];
    const target = EC.url(EC.HOME_PAGE[role]);
    const pageName = role === 'clerk' ? 'Các lần lưu chứng cứ' : 'Lưu chứng';

    document.getElementById('login-success-text').textContent =
      `Xin chào ${user.name}. Đang chuyển đến trang ${pageName}…`;
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
    attemptsLeft = MAX_ATTEMPTS;
    showError();
  } else if (state === 'success') {
    accountInput.value = 'duongsu';
    showSuccess('litigant', { autoRedirect: false });
  }
})(window.EC);
