/* ==========================================================================
   status.js – bảng trạng thái và hàm EC.badge() tạo badge.
   Theo DESIGN.md: badge luôn có đủ icon + chữ + màu, không dùng màu đơn lẻ.
   tone ↔ class CSS: match | mismatch | pending | neutral | empty
   ========================================================================== */

(function (EC) {
  'use strict';

  EC.STATUS = {
    // ---- Trạng thái một lần lưu chứng cứ (biên nhận) ----
    recorded: { label: 'Đã ghi nhận', tone: 'pending', icon: 'clock', hint: 'Sẽ khóa lúc 23:59 cùng ngày' },
    locked: { label: 'Đã khóa', tone: 'neutral', icon: 'lock', hint: 'Không ai sửa được, kể cả Tòa. Chờ Tòa kiểm tra' },
    checked: { label: 'Tòa đã kiểm tra', tone: 'match', icon: 'check', hint: 'Xem kết quả từng file trong chi tiết' },

    // ---- Kết quả từng file (góc nhìn đương sự) ----
    match: { label: 'Trùng khớp', tone: 'match', icon: 'check', hint: 'File không thay đổi' },
    mismatch: { label: 'Không khớp', tone: 'mismatch', icon: 'circle-x', hint: 'File đã bị thay đổi' },
    checking: { label: 'Đang kiểm tra', tone: 'pending', icon: 'clock', hint: 'Tòa đang đối chiếu' },
    unchecked: { label: 'Chưa kiểm tra', tone: 'empty', icon: 'minus', hint: 'Tòa chưa đối chiếu' },

    // ---- Kết quả đối chiếu (góc nhìn thư ký) ----
    notCompared: { label: 'Chưa đối chiếu', tone: 'empty', icon: 'minus' },
    awaitingCompare: { label: 'Chưa đối chiếu', tone: 'empty', icon: 'clock' },
    savedMatch: { label: 'Trùng khớp', tone: 'match', icon: 'check' },
    savedMismatch: { label: 'Không khớp', tone: 'mismatch', icon: 'circle-x' },
  };

  /**
   * Tạo HTML badge.
   * @param {string} key   khóa trong EC.STATUS, vd 'locked'
   * @param {object} [opt] { withHint: true } để hiện tooltip giải thích
   */
  EC.badge = function (key, opt = {}) {
    const s = EC.STATUS[key];
    if (!s) return '';
    const title = opt.withHint && s.hint ? ` title="${EC.escape(s.hint)}"` : '';
    return `<span class="badge badge--${s.tone}"${title}><i data-lucide="${s.icon}"></i>${EC.escape(s.label)}</span>`;
  };
})(window.EC);
