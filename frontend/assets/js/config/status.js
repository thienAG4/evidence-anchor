/* ==========================================================================
   status.js – bảng trạng thái và hàm EC.badge() tạo badge.
   Theo DESIGN.md: badge luôn có đủ icon + chữ + màu, không dùng màu đơn lẻ.
   tone ↔ class CSS: match | mismatch | pending | neutral | empty
   ========================================================================== */

(function (EC) {
  'use strict';

  EC.STATUS = {
    // ---- Trạng thái một lần lưu chứng cứ (biên nhận) ----
    recorded: { label: 'Đã ghi nhận', tone: 'pending', icon: 'clock', hint: 'Chờ neo lên chuỗi công khai, neo xong mới khóa' },
    locked: { label: 'Đã khóa', tone: 'neutral', icon: 'lock', hint: 'Không ai sửa được, kể cả Tòa. Chờ Tòa kiểm tra' },
    checked: { label: 'Tòa đã kiểm tra', tone: 'match', icon: 'check', hint: 'Xem kết quả từng file trong chi tiết' },

    // ---- Kết quả từng file (góc nhìn đương sự) ----
    // Nhãn theo backlog (mục 2.3 brief): KHÔNG THAY ĐỔI / ĐÃ THAY ĐỔI / KHÔNG CÓ MỐC ĐỂ SO.
    // Hint chỉ MÔ TẢ kết quả so sánh, không KẾT LUẬN hộ (thật/giả/ai sửa là việc của Tòa).
    match: { label: 'Khớp bản lưu chứng', tone: 'match', icon: 'check', hint: 'Không phát hiện khác biệt so với bản đã lưu chứng' },
    mismatch: { label: 'Khác bản lưu chứng', tone: 'mismatch', icon: 'circle-x', hint: 'Có khác biệt so với bản đã lưu chứng' },
    checking: { label: 'Đang kiểm tra', tone: 'pending', icon: 'clock', hint: 'Tòa đang đối chiếu' },
    unchecked: { label: 'Chưa kiểm tra', tone: 'empty', icon: 'minus', hint: 'Tòa chưa đối chiếu' },
    noBaseline: { label: 'Không có mốc để so', tone: 'empty', icon: 'file-search', hint: 'Không có lần lưu chứng cứ nào để đối chiếu' },

    // ---- Kết quả đối chiếu (góc nhìn thư ký) ----
    notCompared: { label: 'Chưa đối chiếu', tone: 'empty', icon: 'minus' },
    awaitingCompare: { label: 'Chưa đối chiếu', tone: 'empty', icon: 'clock' },
    savedMatch: { label: 'Khớp bản lưu chứng', tone: 'match', icon: 'check' },
    savedMismatch: { label: 'Khác bản lưu chứng', tone: 'mismatch', icon: 'circle-x' },

    // ---- Từng bước kiểm tra biên nhận (trang công khai) ----
    checkPass: { label: 'Đạt', tone: 'match', icon: 'check' },
    checkFail: { label: 'Không đạt', tone: 'mismatch', icon: 'circle-x' },
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
