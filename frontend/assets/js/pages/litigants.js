/* ==========================================================================
   Trang Đương sự (thư ký) – pages/clerk/litigants.html
   Bấm một hàng → mở danh sách lần lưu chứng cứ, lọc sẵn theo tên đương sự.
   ========================================================================== */

(function (EC) {
  'use strict';
  EC.data.whenReady(() => {

  const searchInput = document.getElementById('filter-search');
  const statusSelect = document.getElementById('filter-status');
  const tableBody = document.getElementById('litigant-table-body');
  const countText = document.getElementById('litigant-count');

  // Ghép dữ liệu đương sự với thống kê lần lưu chứng
  const litigants = EC.data.litigants.map((p) => {
    const receipts = EC.data.receiptsOf(p.name);
    return {
      ...p,
      ...EC.data.litigantSummary(p.name),
      hasPendingLock: receipts.some((r) => r.status === 'recorded'),
      hasUnchecked: receipts.some((r) => r.files.some((f) => f.result === 'unchecked')),
    };
  });

  function render() {
    const keyword = EC.normalize(searchInput.value);
    const status = statusSelect.value;

    const rows = litigants.filter((p) => {
      if (keyword && !EC.normalize(p.name).includes(keyword)) return false;
      if (status === 'pendingLock' && !p.hasPendingLock) return false;
      if (status === 'unchecked' && !p.hasUnchecked) return false;
      return true;
    });

    tableBody.innerHTML = rows.length ? rows.map((p) => `
      <tr data-name="${EC.escape(p.name)}">
        <td>${EC.escape(p.name)}</td>
        <td>${EC.escape(p.username)}</td>
        <td>${EC.escape(p.email)}</td>
        <td class="is-center">${p.receiptCount}</td>
        <td class="is-center">${p.fileCount}</td>
        <td class="is-nowrap">${EC.escape(p.lastAt)}</td>
        <td class="table__chevron"><i data-lucide="chevron-right"></i></td>
      </tr>`).join('')
      : '<tr><td colspan="7" class="table-empty">Không tìm thấy đương sự phù hợp.</td></tr>';

    countText.textContent = `Hiển thị ${rows.length} / ${litigants.length} đương sự`;
    EC.refreshIcons();
  }

  searchInput.addEventListener('input', render);
  statusSelect.addEventListener('change', render);

  tableBody.addEventListener('click', (event) => {
    const row = event.target.closest('tr[data-name]');
    if (row) window.location.href = `submissions.html?q=${encodeURIComponent(row.dataset.name)}`;
  });

  render();
  });
})(window.EC);
