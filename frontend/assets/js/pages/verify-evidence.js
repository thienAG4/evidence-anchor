/* ==========================================================================
   Trang Đối chiếu chứng cứ (thư ký) – pages/clerk/verify-evidence.html?id=TX-0007
   Luồng: bấm "Đối chiếu" ở trang Lần lưu chứng cứ (truyền ?id=)
          → chọn file trong hồ sơ Tòa cho từng mã file
          → xem kết quả → "Lưu kết quả" → xác nhận → khóa kết quả.
   Lần lưu chứng KHÔNG chọn lại được trên trang này.

   Cách so sánh: file Tòa chọn được gửi lên máy chủ, máy chủ băm SHA-256 rồi so với file cùng mã trong
   biên nhận (thư ký không thấy mã băm). Chọn file = xem trước (POST /clerk/receipts/{id}/compare, không ghi);
   "Lưu kết quả" = máy chủ băm lại các file và ghi kết quả kèm giai đoạn (POST …/verifications).
   ========================================================================== */

(function (EC) {
  'use strict';
  EC.data.whenReady(() => {

  const receiptDisplay = document.getElementById('receipt-display');
  const phaseSelect = document.getElementById('phase-select');
  const tableBody = document.getElementById('verify-table-body');
  const progressText = document.getElementById('progress-text');
  const alertBox = document.getElementById('verify-alert');
  const summaryText = document.getElementById('verify-summary');
  const saveWrapper = document.getElementById('save-wrapper');
  const saveButton = document.getElementById('save-button');
  const restartButton = document.getElementById('restart-button');
  const savedBanner = document.getElementById('saved-banner');

  let receipt = null;
  /** Mỗi hàng: { file, chosenName, chosenFile, result: 'match'|'mismatch'|null, locked, computing } */
  let rows = [];
  let savedAt = null;

  phaseSelect.innerHTML = EC.data.verifyPhases.map((p) =>
    `<option>${EC.escape(p)}</option>`).join('');

  /** Ẩn nội dung đối chiếu, hiện thông báo kèm link về danh sách */
  function showUnavailable(message) {
    document.querySelectorAll('.page > .page-section, .page > .page-actions').forEach((el) => { el.hidden = true; });
    document.getElementById('verify-unavailable').hidden = false;
    document.getElementById('verify-unavailable-text').textContent = message;
    document.querySelector('.breadcrumb__current').textContent = 'Đối chiếu';
  }

  function loadReceipt(r) {
    receipt = r;
    receiptDisplay.textContent = `${r.id} · ${r.litigant} · ${r.files.length} file`;
    document.title = `Đối chiếu ${r.id} – EvidenceChain`;

    rows = receipt.files.map((file) => {
      const done = file.result === 'match' || file.result === 'mismatch';
      return { file, chosenName: null, result: done ? file.result : null, locked: done, computing: false };
    });

    document.querySelectorAll('[data-field="receiptId"]').forEach((el) => { el.textContent = receipt.id; });
    document.querySelectorAll('[data-field="recordedAt"]').forEach((el) => { el.textContent = receipt.recordedAt; });
    document.querySelectorAll('[data-field="lockedAt"]').forEach((el) => { el.textContent = receipt.lockedAt; });

    // Khôi phục banner "đã lưu kết quả" nếu lần đối chiếu trước đã lưu (giữ được sau khi F5,
    // vì mốc kiểm tra giờ nằm trong dữ liệu — không còn là biến tạm riêng của lần tải trang này).
    const lastCheckedAt = rows.filter((r) => r.locked && r.file.checkedAt).map((r) => r.file.checkedAt).pop();
    if (lastCheckedAt) {
      savedAt = lastCheckedAt;
      document.querySelector('[data-field="savedAt"]').textContent = savedAt;
    }

    render();
  }

  // ---------------------------------------------------------------- Thống kê
  function stats() {
    const compared = rows.filter((r) => r.result);
    return {
      total: rows.length,
      compared: compared.length,
      match: compared.filter((r) => r.result === 'match').length,
      mismatch: compared.filter((r) => r.result === 'mismatch').length,
      unsaved: rows.filter((r) => r.result && !r.locked).length,
    };
  }

  // ---------------------------------------------------------------- Render
  function fileInputHtml(index) {
    return `<input class="sr-only" type="file" data-index="${index}">`;
  }

  function renderFileCell(row, index) {
    if (row.computing) {
      return '<span class="verify-file__empty">Đang tính mã băm…</span>';
    }
    if (row.locked && !row.chosenName) {
      return '<span class="text-secondary">Đã đối chiếu trước đó</span>';
    }
    if (row.chosenName) {
      return `<div class="verify-file">
          ${EC.fileNameHtml(row.chosenName)}
          ${row.locked ? '' : `<label class="btn btn--link">Đổi file${fileInputHtml(index)}</label>`}
        </div>`;
    }
    return `<div class="verify-file">
        <label class="btn btn--secondary btn--sm"><i data-lucide="file-up" class="icon-sm"></i>Chọn file${fileInputHtml(index)}</label>
        <span class="verify-file__empty">Chưa chọn tệp tương ứng</span>
      </div>`;
  }

  function renderResultCell(row) {
    if (row.locked) {
      const time = row.file.checkedAt
        ? `<span class="verify-result__time">Kiểm tra lúc ${EC.escape(row.file.checkedAt)}</span>` : '';
      return `<div class="verify-result-wrap">
          <span class="verify-result">${EC.badge(row.result === 'match' ? 'savedMatch' : 'savedMismatch')}
            <i data-lucide="lock" class="verify-result__lock" aria-label="Đã khóa"></i></span>
          ${time}
        </div>`;
    }
    return EC.badge(row.result || 'notCompared');
  }

  function renderAlert(s) {
    if (s.compared === 0) {
      alertBox.className = 'alert alert--info verify-alert';
      alertBox.innerHTML = `
        <i data-lucide="info" class="icon-sm"></i>
        <div>
          <p class="alert__text" style="color: var(--color-text)">Chọn đúng file tương ứng trong hồ sơ vụ án. File chỉ được gửi lên để tính mã băm rồi bỏ, không lưu lại.</p>
          <p class="alert__text text-xs">Quá trình kiểm chứng thực hiện tại chỗ bằng thuật toán đối sánh tự động. Tòa án đảm bảo tính bảo mật dữ liệu tuyệt đối theo Nghị định 13/2023/NĐ-CP.</p>
        </div>`;
    } else if (s.mismatch > 0) {
      alertBox.className = 'alert alert--note verify-alert';
      alertBox.innerHTML = `
        <i data-lucide="info" class="icon-sm"></i>
        <div>
          <p class="alert__title alert__title--danger">Có ${s.mismatch} file khác bản lưu chứng</p>
          <p class="alert__text">Hệ thống chỉ ghi nhận kết quả so sánh. Việc chứng cứ có được sử dụng hay không do Thẩm phán và Hội đồng xét xử quyết định.</p>
        </div>`;
    } else {
      alertBox.className = 'alert alert--note verify-alert';
      alertBox.innerHTML = `
        <i data-lucide="info" class="icon-sm"></i>
        <div>
          <p class="alert__title text-success">Các file đã đối chiếu đều khớp bản lưu chứng</p>
          <p class="alert__text">Kết quả chỉ cho biết file hiện tại có khớp với bản đã lưu chứng hay không. Giá trị chứng minh do Tòa án xem xét.</p>
        </div>`;
    }
  }

  function render() {
    tableBody.innerHTML = rows.map((row, i) => `
      <tr>
        <td>
          <span class="verify-table__code">${EC.escape(row.file.code)}</span>
          <span class="table__sub">Tài liệu đương sự nộp #${i + 1}</span>
        </td>
        <td>${renderFileCell(row, i)}</td>
        <td>${renderResultCell(row)}</td>
        <td class="is-right">${row.result && !row.locked
          ? `<button type="button" class="icon-btn" data-clear="${i}" title="Bỏ chọn file" aria-label="Bỏ chọn file"><i data-lucide="x" class="icon-sm"></i></button>`
          : '<span class="text-muted">—</span>'}</td>
      </tr>`).join('');

    const s = stats();
    progressText.textContent = `${s.compared} / ${s.total} file hoàn tất`;
    renderAlert(s);

    summaryText.hidden = s.compared === 0;
    summaryText.textContent = `Đã đối chiếu ${s.compared}/${s.total} file · ${s.match} giống · ${s.mismatch} khác`;

    // Nút lưu: chỉ bật khi có kết quả chưa lưu
    const showSave = s.unsaved > 0 || !savedAt;
    saveWrapper.hidden = !showSave;
    saveButton.disabled = s.unsaved === 0;
    saveButton.lastChild.textContent = s.unsaved ? 'Lưu kết quả' : 'Lưu kết quả kiểm tra';
    saveWrapper.title = s.unsaved ? '' : 'Chọn ít nhất một file để đối chiếu';
    restartButton.hidden = showSave;

    // Sau khi đã lưu: khóa thông tin đối chiếu
    savedBanner.hidden = !savedAt;
    phaseSelect.disabled = Boolean(savedAt);
    phaseSelect.closest('.input-group').classList.toggle('input-group--disabled', Boolean(savedAt));

    EC.refreshIcons();
  }

  // ---------------------------------------------------------------- So sánh file
  async function compareFile(index, file) {
    const row = rows[index];
    row.computing = true;
    render();

    try {
      row.result = await EC.data.compare(receipt.id, row.file.code, file);
      row.chosenName = file.name;
      row.chosenFile = file; // giữ lại để gửi lên khi "Lưu kết quả" (máy chủ băm lại, không tin kết quả trình duyệt)
    } catch (err) {
      alert(err.message); // vd file .exe bị từ chối, chưa khóa, mất kết nối
    } finally {
      row.computing = false;
      render();
    }
  }

  tableBody.addEventListener('change', (event) => {
    const input = event.target.closest('input[type="file"][data-index]');
    if (input && input.files[0]) compareFile(Number(input.dataset.index), input.files[0]);
  });

  tableBody.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-clear]');
    if (!btn) return;
    const row = rows[Number(btn.dataset.clear)];
    row.result = null;
    row.chosenName = null;
    row.chosenFile = null;
    render();
  });

  // ---------------------------------------------------------------- Lưu kết quả
  function openConfirm() {
    const s = stats();
    const modal = document.getElementById('modal-confirm-save');
    const set = (name, value) => { modal.querySelector(`[data-field="${name}"]`).textContent = value; };
    set('receiptId', receipt.id);
    set('phase', phaseSelect.value);
    set('matchCount', s.match);
    set('mismatchCount', s.mismatch);
    set('pendingCount', s.total - s.compared);
    EC.modal.open('modal-confirm-save');
  }

  async function saveResults() {
    const pending = rows.filter((row) => row.result && !row.locked && row.chosenFile);
    const confirmButton = document.getElementById('confirm-save-button');
    confirmButton.disabled = true;
    try {
      const updated = await EC.data.saveVerification(
        receipt.id, phaseSelect.value, pending.map((row) => ({ code: row.file.code, file: row.chosenFile })));
      // Lấy kết quả + giờ kiểm tra do máy chủ ghi → đương sự thấy cùng kết quả
      pending.forEach((row) => {
        const saved = updated.files.find((f) => f.code === row.file.code);
        row.file = saved;
        row.result = saved.result;
        row.locked = true;
      });
      receipt = updated;
      savedAt = pending.length ? pending[pending.length - 1].file.checkedAt : EC.nowText();
      document.querySelector('[data-field="savedAt"]').textContent = savedAt;
      EC.modal.close('modal-confirm-save');
      render();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      EC.modal.close('modal-confirm-save');
      alert(`Chưa lưu được kết quả: ${err.message}`);
    } finally {
      confirmButton.disabled = false;
    }
  }

  saveButton.addEventListener('click', openConfirm);
  document.getElementById('confirm-save-button').addEventListener('click', saveResults);

  // ---------------------------------------------------------------- Khởi tạo
  const state = EC.param('state');
  const id = EC.param('id');
  const found = id ? EC.data.getReceipt(id) : null;

  if (!id) {
    showUnavailable('Chưa chọn lần lưu chứng cứ. Vui lòng bấm "Đối chiếu" tại một lần lưu chứng cứ trong danh sách.');
    return;
  }
  if (!found) {
    // Không có mốc để so: không có lần lưu chứng cứ (sự kiện A) nào ứng với mã này trong các vụ mình phụ trách
    showUnavailable(`Không có mốc để so: không có lần lưu chứng cứ nào với mã ${id} thuộc đương sự trong vụ án bạn phụ trách.`);
    return;
  }
  if (found.status === 'recorded') {
    showUnavailable(`Lần lưu chứng cứ ${found.id} chưa khóa (chưa neo lên chuỗi). Chỉ đối chiếu được sau khi đã khóa.`);
    return;
  }

  loadReceipt(found);

  // Xem trước giao diện (?state=result|confirm) trên một biên nhận thật; KHÔNG gửi gì lên máy chủ.
  // (Bỏ ?state=saved: lưu kết quả cần file thật để máy chủ băm.)
  if (state && rows.length >= 2) {
    const first = rows[0];
    const second = rows[1];
    first.chosenName = first.file.name;
    first.result = 'match';
    second.chosenName = second.file.name.replace(/\.[^.]+$/, '_zalo.jpg');
    second.result = 'mismatch';
    render();
    if (state === 'confirm') openConfirm();
  }
  });
})(window.EC);
