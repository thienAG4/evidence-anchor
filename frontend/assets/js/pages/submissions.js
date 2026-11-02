/* ==========================================================================
   Trang Các lần lưu chứng cứ (thư ký) – pages/clerk/submissions.html
   - Lọc theo từ khóa, trạng thái, khoảng ngày.
   - Bấm một hàng (hoặc mũi tên ">") → mở drawer xem nhanh.
   - Nút "Đối chiếu" → trang verify-evidence.html?id=…
   Mở sẵn drawer: ?open=TX-0007   ·   Lọc sẵn theo tên: ?q=Trần Thị Lan
   ========================================================================== */

(function (EC) {
  'use strict';

  const LOCK_HINT = 'Chờ khóa lúc 23:59 hôm nay mới đối chiếu được';

  // Góc nhìn thư ký: tên trạng thái của từng file
  const FILE_STATUS_FOR_CLERK = {
    match: 'savedMatch',
    mismatch: 'savedMismatch',
    checking: 'checking',
    unchecked: 'awaitingCompare',
  };

  const searchInput = document.getElementById('filter-search');
  const statusSelect = document.getElementById('filter-status');
  const dateInput = document.getElementById('filter-date');
  const tableBody = document.getElementById('submission-table-body');
  const countText = document.getElementById('submission-count');

  const verifyUrl = (id) => `verify-evidence.html?id=${encodeURIComponent(id)}`;
  const canVerify = (r) => r.status !== 'recorded';

  // ---------------------------------------------------------------- Lọc
  function getFilteredReceipts() {
    const keyword = EC.normalize(searchInput.value);
    const status = statusSelect.value;
    const range = dateInput.value; // { from, to } từ <date-range-picker>

    return EC.data.receipts.filter((r) => {
      if (keyword && !EC.normalize(`${r.id} ${r.litigant}`).includes(keyword)) return false;
      if (status && r.status !== status) return false;
      if (range.from) {
        const day = EC.parseDate(r.recordedAt);
        if (day < range.from || day > range.to) return false;
      }
      return true;
    });
  }

  // ---------------------------------------------------------------- Bảng
  function renderTable() {
    const rows = getFilteredReceipts();

    tableBody.innerHTML = rows.length ? rows.map((r) => `
      <tr data-id="${EC.escape(r.id)}">
        <td>${EC.escape(r.id)}</td>
        <td>${EC.escape(r.litigant)}</td>
        <td class="is-center">${r.files.length}</td>
        <td class="is-nowrap">${EC.escape(r.recordedAt)}</td>
        <td>${EC.badge(r.status, { withHint: true })}</td>
        <td>${canVerify(r)
          ? `<a class="btn btn--outline btn--sm" href="${verifyUrl(r.id)}"><i data-lucide="arrow-left-right" class="icon-sm"></i>Đối chiếu</a>`
          : `<span class="submission-action" title="${LOCK_HINT}" aria-disabled="true"><button type="button" class="btn btn--sm" disabled><i data-lucide="arrow-left-right" class="icon-sm"></i>Đối chiếu</button></span>`}
        </td>
        <td class="table__chevron"><i data-lucide="chevron-right"></i></td>
      </tr>`).join('')
      : '<tr><td colspan="7" class="table-empty">Không có lần lưu chứng cứ nào phù hợp bộ lọc.</td></tr>';

    countText.textContent = `Hiển thị ${rows.length} / ${EC.data.receipts.length} lần lưu chứng cứ`;
    EC.refreshIcons();
  }

  searchInput.addEventListener('input', renderTable);
  statusSelect.addEventListener('change', renderTable);
  dateInput.addEventListener('change', renderTable);

  tableBody.addEventListener('click', (event) => {
    if (event.target.closest('a, button, .submission-action')) return;
    const row = event.target.closest('tr[data-id]');
    if (row) openDrawer(row.dataset.id);
  });

  // ---------------------------------------------------------------- Drawer
  function buildTimeline(r) {
    const isLocked = r.status !== 'recorded';
    const compared = r.files.filter((f) => f.result === 'match' || f.result === 'mismatch').length;

    const items = [
      { title: 'Đã ghi nhận', desc: `${r.recordedAt} · Hệ thống của Tòa ghi nhận`, done: true },
      {
        title: 'Đã khóa, không thể sửa',
        desc: isLocked ? `${r.lockedAt} · Từ đây không ai sửa được, kể cả Tòa` : `Sẽ khóa lúc ${r.lockedAt}`,
        done: isLocked,
      },
      {
        title: 'Tòa đã kiểm tra',
        desc: compared ? `Đã đối chiếu ${compared}/${r.files.length} file` : 'Chưa có file nào được đối chiếu',
        done: r.status === 'checked',
      },
    ];

    return `<ol class="timeline">${items.map((it) => `
      <li class="timeline__item ${it.done ? 'is-done' : 'is-pending'}">
        <span class="timeline__icon">${it.done ? '<i data-lucide="check" class="icon-sm"></i>' : '<span class="timeline__dot"></span>'}</span>
        <div>
          <p class="timeline__title">${it.title}</p>
          <p class="timeline__desc">${EC.escape(it.desc)}</p>
        </div>
      </li>`).join('')}</ol>`;
  }

  function openDrawer(id) {
    const r = EC.data.getReceipt(id);
    if (!r) return;

    document.getElementById('drawer-title').textContent = `Lần lưu chứng cứ ${r.id}`;
    document.getElementById('drawer-status').innerHTML = EC.badge(r.status, { withHint: true });

    document.getElementById('drawer-body').innerHTML = `
      <section class="drawer__section">
        <dl class="kv-list kv-list--plain">
          <div class="kv-list__row"><dt class="kv-list__label">Đương sự</dt><dd class="kv-list__value">${EC.escape(r.litigant)}</dd></div>
          <div class="kv-list__row"><dt class="kv-list__label">Số file</dt><dd class="kv-list__value">${r.files.length}</dd></div>
        </dl>
      </section>
      <section class="drawer__section">
        <h3 class="drawer__section-title">Tiến trình</h3>
        ${buildTimeline(r)}
      </section>
      <section class="drawer__section">
        <h3 class="drawer__section-title">Mã file</h3>
        ${r.files.map((f) => `
          <div class="drawer-file">
            <span class="drawer-file__code"><i data-lucide="file"></i>${EC.escape(f.code)}</span>
            ${EC.badge(FILE_STATUS_FOR_CLERK[f.result])}
          </div>`).join('')}
      </section>
      <div class="alert alert--info">
        <i data-lucide="info" class="icon-sm"></i>
        <p>Hệ thống chỉ lưu dấu vết của file, không lưu nội dung file.</p>
      </div>`;

    const verifyBtn = document.getElementById('drawer-verify');
    verifyBtn.href = verifyUrl(r.id);
    verifyBtn.toggleAttribute('aria-disabled', !canVerify(r));
    if (!canVerify(r)) verifyBtn.setAttribute('aria-disabled', 'true');
    verifyBtn.title = canVerify(r) ? '' : LOCK_HINT;

    EC.refreshIcons();
    EC.drawer.open('drawer-submission');
  }

  // ---------------------------------------------------------------- Khởi tạo
  searchInput.value = EC.param('q') || '';
  renderTable();
  const openId = EC.param('open');
  if (openId) openDrawer(openId);
})(window.EC);
