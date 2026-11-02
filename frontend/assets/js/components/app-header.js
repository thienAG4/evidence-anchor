/* ==========================================================================
   <app-header role="litigant|clerk"></app-header>
   - Không có role  → header công khai (trang đăng nhập), không hiện người dùng.
   - Có role        → hiện tên, vai trò và menu thả xuống (Hồ sơ / Đăng xuất).
   CSS: assets/css/layout/header.css
   ========================================================================== */

(function (EC) {
  'use strict';

  class AppHeader extends HTMLElement {
    connectedCallback() {
      const role = this.getAttribute('role');
      const user = role ? EC.USERS[role] : null;
      const homeHref = EC.url(role ? EC.HOME_PAGE[role] : EC.LOGIN_PAGE);

      this.innerHTML = `
        <header class="site-header">
          <a class="site-header__brand" href="${homeHref}">
            <img class="site-header__logo" src="${EC.url('assets/images/logo.png')}" alt="Logo EvidenceChain">
            <span class="site-header__title">EvidenceChain – Hệ thống lưu chứng cứ điện tử</span>
          </a>
          ${user ? this.renderUserMenu(user) : ''}
        </header>`;

      if (user) this.bindUserMenu();
    }

    renderUserMenu(user) {
      return `
        <div class="user-menu">
          <button type="button" class="user-menu__toggle" aria-haspopup="menu" aria-expanded="false">
            <span class="user-menu__avatar"><i data-lucide="user" class="icon-sm"></i></span>
            <span class="user-menu__info">
              <span class="user-menu__name">${EC.escape(user.name)}</span>
              <span class="user-menu__role">${EC.escape(user.roleLabel)}</span>
            </span>
            <i data-lucide="chevron-down" class="user-menu__chevron icon-sm"></i>
          </button>
          <div class="user-menu__dropdown" role="menu" hidden>
            <a class="user-menu__item" role="menuitem" href="#">
              <i data-lucide="user" class="icon-sm"></i>Hồ sơ cá nhân
            </a>
            <div class="user-menu__divider"></div>
            <a class="user-menu__item user-menu__item--danger" role="menuitem" href="${EC.url(EC.LOGIN_PAGE)}">
              <i data-lucide="log-out" class="icon-sm"></i>Đăng xuất
            </a>
          </div>
        </div>`;
    }

    bindUserMenu() {
      const menu = this.querySelector('.user-menu');
      const toggle = menu.querySelector('.user-menu__toggle');
      const dropdown = menu.querySelector('.user-menu__dropdown');

      const setOpen = (open) => {
        dropdown.hidden = !open;
        menu.classList.toggle('is-open', open);
        toggle.setAttribute('aria-expanded', String(open));
      };

      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        setOpen(dropdown.hidden);
      });
      document.addEventListener('click', (e) => {
        if (!menu.contains(e.target)) setOpen(false);
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') setOpen(false);
      });
    }
  }

  customElements.define('app-header', AppHeader);
})(window.EC);
