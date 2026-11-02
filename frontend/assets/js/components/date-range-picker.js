/* ==========================================================================
   <date-range-picker placeholder="Từ ngày – Đến ngày"></date-range-picker>
   Bộ chọn KHOẢNG NGÀY (chỉ ngày/tháng/năm, không có giờ:phút).

   - Bấm vào ô → mở lịch. Bấm ngày thứ nhất = "Từ ngày", ngày thứ hai = "Đến ngày".
   - "Áp dụng" → đóng lịch, phát sự kiện `change`. "Xóa" → bỏ lọc.
   - Đọc giá trị: picker.value → { from: Date|null, to: Date|null }
   CSS: assets/css/components/date-range-picker.css
   ========================================================================== */

(function (EC) {
  'use strict';

  const WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
  const pad = (n) => String(n).padStart(2, '0');
  const fmt = (d) => `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
  const sameDay = (a, b) => a && b && a.getTime() === b.getTime();
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

  class DateRangePicker extends HTMLElement {
    connectedCallback() {
      if (this._ready) return;
      this._ready = true;

      this.from = null;          // giá trị đã áp dụng
      this.to = null;
      this.draftFrom = null;     // giá trị đang chọn trong lịch
      this.draftTo = null;
      this.hoverDay = null;
      this.viewMonth = startOfDay(new Date());
      this.viewMonth.setDate(1);

      const placeholder = this.getAttribute('placeholder') || 'Từ ngày – Đến ngày';
      this.innerHTML = `
        <div class="date-range">
          <button type="button" class="input-group date-range__trigger" aria-haspopup="dialog" aria-expanded="false">
            <i data-lucide="calendar" class="input-group__icon"></i>
            <span class="date-range__text is-placeholder" data-placeholder="${EC.escape(placeholder)}">${EC.escape(placeholder)}</span>
          </button>
          <button type="button" class="date-range__clear icon-btn" aria-label="Bỏ lọc theo ngày" hidden>
            <i data-lucide="x" class="icon-sm"></i>
          </button>

          <div class="date-range__popover" role="dialog" aria-label="Chọn khoảng ngày" hidden>
            <div class="date-range__head">
              <button type="button" class="icon-btn" data-nav="-1" aria-label="Tháng trước"><i data-lucide="chevron-left" class="icon-sm"></i></button>
              <span class="date-range__month"></span>
              <button type="button" class="icon-btn" data-nav="1" aria-label="Tháng sau"><i data-lucide="chevron-right" class="icon-sm"></i></button>
            </div>
            <div class="date-range__weekdays">${WEEKDAYS.map((d) => `<span>${d}</span>`).join('')}</div>
            <div class="date-range__grid" role="grid"></div>
            <p class="date-range__hint"></p>
            <div class="date-range__footer">
              <button type="button" class="btn btn--secondary btn--sm" data-action="clear">Xóa</button>
              <button type="button" class="btn btn--primary btn--sm" data-action="apply">Áp dụng</button>
            </div>
          </div>
        </div>`;

      this.trigger = this.querySelector('.date-range__trigger');
      this.text = this.querySelector('.date-range__text');
      this.clearBtn = this.querySelector('.date-range__clear');
      this.panel = this.querySelector('.date-range__popover');
      this.grid = this.querySelector('.date-range__grid');
      this.monthLabel = this.querySelector('.date-range__month');
      this.hint = this.querySelector('.date-range__hint');

      this.bindEvents();
    }

    /** Giá trị đã áp dụng */
    get value() {
      return { from: this.from, to: this.to };
    }

    // ------------------------------------------------------------ Sự kiện
    bindEvents() {
      this.trigger.addEventListener('click', () => (this.panel.hidden ? this.open() : this.close()));

      this.clearBtn.addEventListener('click', () => this.commit(null, null));

      this.panel.addEventListener('click', (e) => {
        const nav = e.target.closest('[data-nav]');
        const day = e.target.closest('[data-day]');
        const action = e.target.closest('[data-action]');

        if (nav) {
          this.viewMonth.setMonth(this.viewMonth.getMonth() + Number(nav.dataset.nav));
          this.renderCalendar();
        } else if (day) {
          this.pickDay(new Date(Number(day.dataset.day)));
        } else if (action && action.dataset.action === 'clear') {
          this.commit(null, null);
        } else if (action && action.dataset.action === 'apply') {
          this.commit(this.draftFrom, this.draftTo || this.draftFrom);
        }
      });

      // Xem trước khoảng ngày khi rê chuột
      this.grid.addEventListener('mouseover', (e) => {
        const day = e.target.closest('[data-day]');
        if (!day || !this.draftFrom || this.draftTo) return;
        this.hoverDay = new Date(Number(day.dataset.day));
        this.paintRange();
      });

      // Bấm ra ngoài → đóng lịch. Dùng composedPath() vì khi chọn ngày, lưới lịch
      // được vẽ lại nên nút vừa bấm đã bị gỡ khỏi trang.
      document.addEventListener('click', (e) => {
        if (!this.panel.hidden && !e.composedPath().includes(this)) this.close();
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !this.panel.hidden) {
          this.close();
          this.trigger.focus();
        }
      });
    }

    open() {
      this.draftFrom = this.from;
      this.draftTo = this.to;
      this.hoverDay = null;
      const base = this.from || new Date();
      this.viewMonth = new Date(base.getFullYear(), base.getMonth(), 1);
      this.panel.hidden = false;
      this.trigger.setAttribute('aria-expanded', 'true');
      this.renderCalendar();
    }

    close() {
      this.panel.hidden = true;
      this.trigger.setAttribute('aria-expanded', 'false');
    }

    pickDay(day) {
      if (!this.draftFrom || this.draftTo) {
        // Bắt đầu khoảng mới
        this.draftFrom = day;
        this.draftTo = null;
      } else if (day < this.draftFrom) {
        this.draftTo = this.draftFrom;
        this.draftFrom = day;
      } else {
        this.draftTo = day;
      }
      this.hoverDay = null;
      this.renderCalendar();
    }

    /** Lưu giá trị, cập nhật ô hiển thị và báo cho trang biết */
    commit(from, to) {
      this.from = from;
      this.to = to;
      if (from) {
        this.text.textContent = sameDay(from, to) ? fmt(from) : `${fmt(from)} – ${fmt(to)}`;
        this.text.classList.remove('is-placeholder');
      } else {
        this.text.textContent = this.text.dataset.placeholder;
        this.text.classList.add('is-placeholder');
      }
      this.clearBtn.hidden = !from;
      this.close();
      this.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // ------------------------------------------------------------ Vẽ lịch
    renderCalendar() {
      const year = this.viewMonth.getFullYear();
      const month = this.viewMonth.getMonth();
      this.monthLabel.textContent = `Tháng ${month + 1}, ${year}`;

      const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7; // T2 = 0
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const today = startOfDay(new Date());

      let html = '<span class="date-range__blank"></span>'.repeat(firstWeekday);
      for (let d = 1; d <= daysInMonth; d++) {
        const date = new Date(year, month, d);
        html += `<button type="button" class="date-range__day${sameDay(date, today) ? ' is-today' : ''}"
                   data-day="${date.getTime()}" aria-label="${fmt(date)}">${d}</button>`;
      }
      this.grid.innerHTML = html;
      this.paintRange();
      EC.refreshIcons();
    }

    /** Tô màu ngày bắt đầu / kết thúc / các ngày ở giữa */
    paintRange() {
      const from = this.draftFrom;
      const to = this.draftTo || this.hoverDay;
      const [lo, hi] = from && to && to < from ? [to, from] : [from, to];

      this.grid.querySelectorAll('[data-day]').forEach((btn) => {
        const t = Number(btn.dataset.day);
        const isStart = lo && t === lo.getTime();
        const isEnd = hi && t === hi.getTime();
        btn.classList.toggle('is-start', Boolean(isStart));
        btn.classList.toggle('is-end', Boolean(isEnd));
        btn.classList.toggle('is-in-range', Boolean(lo && hi && t > lo.getTime() && t < hi.getTime()));
        btn.setAttribute('aria-pressed', String(Boolean(isStart || isEnd)));
      });

      if (!this.draftFrom) {
        this.hint.textContent = 'Chọn ngày bắt đầu';
      } else if (!this.draftTo) {
        this.hint.textContent = `Từ ${fmt(this.draftFrom)} – chọn ngày kết thúc`;
      } else {
        this.hint.textContent = `Từ ${fmt(this.draftFrom)} đến ${fmt(this.draftTo)}`;
      }
    }
  }

  customElements.define('date-range-picker', DateRangePicker);
})(window.EC);
