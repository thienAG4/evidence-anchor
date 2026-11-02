/* ==========================================================================
   ui.js – điều khiển Modal và Drawer dùng chung.
   - Mở:   EC.modal.open('modal-id')   / EC.drawer.open('drawer-id')
   - Đóng: EC.modal.close('modal-id')  / nút có [data-close], phím Esc,
           hoặc bấm ra vùng tối bên ngoài.
   ========================================================================== */

(function (EC) {
  'use strict';

  function lockScroll() {
    document.body.classList.add('is-locked');
  }

  function unlockScroll() {
    if (!document.querySelector('.modal:not([hidden]), .drawer:not([hidden])')) {
      document.body.classList.remove('is-locked');
    }
  }

  function createController(selector) {
    return {
      open(id) {
        const el = document.getElementById(id);
        if (!el) return;
        el.hidden = false;
        lockScroll();
        const focusTarget = el.querySelector('[data-autofocus]') || el.querySelector('button, a, input, select');
        if (focusTarget) focusTarget.focus();
      },
      close(id) {
        const el = typeof id === 'string' ? document.getElementById(id) : id;
        if (!el) return;
        el.hidden = true;
        el.dispatchEvent(new CustomEvent('ec:close'));
        unlockScroll();
      },
      closeAll() {
        document.querySelectorAll(selector + ':not([hidden])').forEach((el) => this.close(el));
      },
    };
  }

  EC.modal = createController('.modal');
  EC.drawer = createController('.drawer');

  // Nút [data-close] → đóng modal/drawer chứa nó
  document.addEventListener('click', (event) => {
    const closeBtn = event.target.closest('[data-close]');
    if (closeBtn) {
      const host = closeBtn.closest('.modal, .drawer');
      if (host) (host.classList.contains('modal') ? EC.modal : EC.drawer).close(host);
      return;
    }
    // Bấm vào vùng tối (chính phần tử .modal / .drawer, không phải nội dung bên trong)
    if (event.target.matches('.modal[data-dismissible], .drawer')) {
      (event.target.classList.contains('modal') ? EC.modal : EC.drawer).close(event.target);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('.modal[data-dismissible]:not([hidden])').forEach((el) => EC.modal.close(el));
    EC.drawer.closeAll();
  });
})(window.EC);
