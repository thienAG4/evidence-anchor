/* ==========================================================================
   <app-footer></app-footer>
   CSS: assets/css/layout/footer.css
   ========================================================================== */

(function () {
  'use strict';

  class AppFooter extends HTMLElement {
    connectedCallback() {
      this.innerHTML = `
        <footer class="site-footer">
          <span>© ${new Date().getFullYear()} EvidenceChain – Team 2, UEL</span>
        </footer>`;
    }
  }

  customElements.define('app-footer', AppFooter);
})();
