/* ==========================================================================
   <app-sidebar role="litigant|clerk" active="submit"></app-sidebar>
   Menu lấy từ EC.NAVIGATION (assets/js/config/navigation.js).
   `active` = key của mục đang chọn (tô đỏ + vạch trái).
   CSS: assets/css/layout/sidebar.css
   ========================================================================== */

(function (EC) {
  'use strict';

  class AppSidebar extends HTMLElement {
    connectedCallback() {
      const items = EC.NAVIGATION[this.getAttribute('role')] || [];
      const active = this.getAttribute('active');

      const links = items.map((item) => {
        const isActive = item.key === active;
        return `
          <a class="sidebar__link${isActive ? ' is-active' : ''}" href="${EC.url(item.href)}"${isActive ? ' aria-current="page"' : ''}>
            <i data-lucide="${item.icon}"></i>
            <span>${EC.escape(item.label)}</span>
          </a>`;
      }).join('');

      this.innerHTML = `
        <aside class="sidebar">
          <nav class="sidebar__nav" aria-label="Điều hướng chính">${links}</nav>
        </aside>`;
    }
  }

  customElements.define('app-sidebar', AppSidebar);
})(window.EC);
