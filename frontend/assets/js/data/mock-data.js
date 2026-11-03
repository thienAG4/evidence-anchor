/* ==========================================================================
   mock-data.js – DỮ LIỆU MẪU để dựng giao diện.
   Khi nối backend (receipt.py / chain.py), thay các mảng dưới đây bằng
   dữ liệu gọi API; các trang chỉ đọc qua EC.data nên không phải sửa nhiều.
   ========================================================================== */

(function (EC) {
  'use strict';

  const receipts = [
    {
      id: 'TX-0001', litigant: 'Nguyễn Thu Minh', status: 'checked',
      recordedAt: '14:20 05/03/2026', lockedAt: '23:59 05/03/2026',
      files: [{ name: 'don_khoi_kien.pdf', result: 'match', checkedAt: '09:00 06/03/2026' }],
    },
    {
      id: 'TX-0003', litigant: 'Nguyễn Thu Minh', status: 'checked',
      recordedAt: '09:15 06/03/2026', lockedAt: '23:59 06/03/2026',
      files: [
        { name: 'tin_nhan_zalo.png', result: 'match', checkedAt: '10:30 07/03/2026' },
        { name: 'video_cuoc_hop.mp4', result: 'mismatch', checkedAt: '10:32 07/03/2026' },
        { name: 'hop_dong_goc.pdf', result: 'checking' },
        { name: 'ghi_am_lan.m4a', result: 'match', checkedAt: '10:35 07/03/2026' },
        { name: 'sao_ke.pdf', result: 'unchecked' },
      ],
    },
    {
      id: 'TX-0005', litigant: 'Trần Thị Lan', status: 'checked',
      recordedAt: '16:40 12/08/2026', lockedAt: '23:59 12/08/2026',
      files: [{ name: 'giay_vay_tien.jpg', result: 'match', checkedAt: '09:10 13/08/2026' }],
    },
    {
      id: 'TX-0007', litigant: 'Nguyễn Thu Minh', status: 'locked',
      recordedAt: '10:15 31/10/2026', lockedAt: '23:59 31/10/2026',
      files: [
        { name: 'hop_dong_vay.pdf', result: 'unchecked' },
        { name: 'anh_chuyen_khoan.png', result: 'unchecked' },
        { name: 'ghi_am_cuoc_goi.m4a', result: 'unchecked' },
      ],
    },
    {
      id: 'TX-0008', litigant: 'Trần Thị Lan', status: 'locked',
      recordedAt: '11:02 31/10/2026', lockedAt: '23:59 31/10/2026',
      files: [
        { name: 'bien_ban_ban_giao.pdf', result: 'unchecked' },
        { name: 'anh_hien_truong.jpg', result: 'unchecked' },
      ],
    },
    {
      id: 'TX-0009', litigant: 'Nguyễn Thu Minh', status: 'locked',
      recordedAt: '21:12 01/11/2026', lockedAt: '23:59 01/11/2026',
      files: [
        { name: 'phu_luc_hop_dong.pdf', result: 'unchecked' },
        { name: 'tin_nhan_doi_no.png', result: 'unchecked' },
      ],
    },
    {
      id: 'TX-0010', litigant: 'Nguyễn Thu Minh', status: 'recorded',
      recordedAt: '21:12 02/11/2026', lockedAt: '23:59 02/11/2026',
      files: [
        { name: 'hop_dong_vay.pdf', result: 'unchecked' },
        { name: 'anh_chuyen_khoan.png', result: 'unchecked' },
        { name: 'ghi_am_cuoc_goi.m4a', result: 'unchecked' },
      ],
    },
  ];

  // Biên nhận do người dùng tạo trên trình duyệt này (trang Lưu chứng cứ)
  // được giữ trong localStorage để các trang khác cùng thấy.
  const STORAGE_KEY = 'evidencechain.newReceipts';

  function loadSavedReceipts() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function assignFileCodes(receipt) {
    receipt.files.forEach((f, i) => {
      f.code = `${receipt.id}-${String(i + 1).padStart(2, '0')}`;
    });
    return receipt;
  }

  // ---------------------------------------------------------------- Tự khóa lúc 23:59
  /** "HH:mm dd/MM/yyyy" → Date */
  function parseDateTime(text) {
    const m = String(text).match(/(\d{1,2}):(\d{2})\s+(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    return m ? new Date(Number(m[5]), Number(m[4]) - 1, Number(m[3]), Number(m[1]), Number(m[2]), 59) : null;
  }

  /**
   * Quy tắc nghiệp vụ: lần lưu chứng cứ "Đã ghi nhận" tự chuyển "Đã khóa"
   * khi qua thời điểm lockedAt (23:59 ngày ghi nhận). Không ai bấm khóa tay.
   * Khi có backend, việc này do máy chủ làm; frontend chỉ đọc trạng thái.
   */
  function applyAutoLock(receipt) {
    if (receipt.status === 'recorded') {
      const lockAt = parseDateTime(receipt.lockedAt);
      if (lockAt && lockAt <= new Date()) receipt.status = 'locked';
    }
    return receipt;
  }

  const seedIds = new Set(receipts.map((r) => r.id)); // dữ liệu mẫu, không lưu localStorage

  receipts.push(...loadSavedReceipts());
  receipts.forEach(assignFileCodes);
  receipts.forEach(applyAutoLock);

  /** Ghi lại các biên nhận người dùng tạo (kèm thay đổi trạng thái/kết quả) */
  function persistSavedReceipts() {
    try {
      const own = receipts.filter((r) => !seedIds.has(r.id));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(own));
    } catch (e) { /* trình duyệt chặn localStorage */ }
  }

  const litigants = [
    { name: 'Nguyễn Thu Minh', idNumber: '0790••••1234', phone: '0912•••678' },
    { name: 'Trần Thị Lan', idNumber: '0791••••5678', phone: '0987•••321' },
  ];

  /** Các giai đoạn tố tụng khi đối chiếu */
  const verifyPhases = [
    'Phiên họp kiểm tra chứng cứ',
    'Trước khi gửi giám định',
    'Phiên tòa sơ thẩm',
    'Phiên tòa phúc thẩm',
  ];

  EC.data = {
    receipts,
    litigants,
    verifyPhases,

    getReceipt(id) {
      const r = receipts.find((x) => x.id === id);
      return r ? applyAutoLock(r) : null;
    },

    receiptsOf(litigantName) {
      return receipts.filter((r) => r.litigant === litigantName);
    },

    /** Thống kê theo đương sự: số lần lưu, tổng file, lần gần nhất */
    litigantSummary(name) {
      const list = receipts.filter((r) => r.litigant === name);
      return {
        receiptCount: list.length,
        fileCount: list.reduce((sum, r) => sum + r.files.length, 0),
        lastAt: list.length ? list[list.length - 1].recordedAt : '—',
      };
    },

    /** Mã biên nhận kế tiếp, vd TX-0011 */
    nextReceiptId() {
      const max = Math.max(...receipts.map((r) => Number(r.id.slice(3))));
      return 'TX-' + String(max + 1).padStart(4, '0');
    },

    /** Thêm biên nhận mới và lưu vào localStorage */
    addReceipt(receipt) {
      assignFileCodes(receipt);
      receipts.push(receipt);
      persistSavedReceipts();
      return receipt;
    },

    /** Lưu thay đổi của một biên nhận (vd kết quả đối chiếu) để các trang khác cùng thấy */
    saveReceipt() {
      persistSavedReceipts();
    },

    /**
     * CHỈ ĐỂ TEST: khóa ngay một lần lưu chứng cứ thay vì chờ 23:59.
     * Gõ trong Console (F12): EC.data.lockNow('TX-0012')
     */
    lockNow(id) {
      const r = receipts.find((x) => x.id === id);
      if (!r) return `Không tìm thấy ${id}`;
      r.lockedAt = EC.nowText();
      r.status = 'locked';
      persistSavedReceipts();
      return `${id} đã chuyển sang "Đã khóa" lúc ${r.lockedAt}. Tải lại trang (F5) để xem.`;
    },

    /** Xóa các biên nhận đã tạo thử, trở về dữ liệu mẫu ban đầu */
    resetSavedReceipts() {
      // Bỏ cả bản trong bộ nhớ, nếu không lần ghi sau sẽ ghi chúng trở lại
      for (let i = receipts.length - 1; i >= 0; i--) {
        if (!seedIds.has(receipts[i].id)) receipts.splice(i, 1);
      }
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (e) { /* bỏ qua */ }
    },
  };

  // CHỈ ĐỂ TEST: mở trang bất kỳ kèm ?lock=TX-0012 để khóa ngay lần lưu chứng đó.
  // Chạy trước khi trang vẽ bảng nên hiện "Đã khóa" luôn; sau đó xóa tham số khỏi URL.
  const lockParam = new URLSearchParams(window.location.search).get('lock');
  if (lockParam) {
    console.info(EC.data.lockNow(lockParam));
    const url = new URL(window.location.href);
    url.searchParams.delete('lock');
    history.replaceState(null, '', url);
  }
})(window.EC);
