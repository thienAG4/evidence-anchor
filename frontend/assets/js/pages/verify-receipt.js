/* ==========================================================================
   Trang Kiểm tra biên nhận (công khai) – pages/public/verify-receipt.html
   Chọn biên nhận .json + file gốc → POST /verify (không cần đăng nhập) → từng bước kiểm tra Đạt / Không đạt:
   chữ ký hệ thống, file khớp hash, tính lại Ha/Habc/Bundle, đường dẫn Merkle, giao dịch trên Sepolia.
   ========================================================================== */

(function (EC) {
  'use strict';

  const receiptInput = document.getElementById('receipt-input');
  const receiptName = document.getElementById('receipt-name');
  const filesInput = document.getElementById('files-input');
  const filesList = document.getElementById('files-list');
  const verifyButton = document.getElementById('verify-button');
  const verifyLabel = document.getElementById('verify-label');
  const resultBox = document.getElementById('verify-result');
  const summary = document.getElementById('verify-summary');
  const checksList = document.getElementById('verify-checks');

  let receiptFile = null;
  let files = [];

  function render() {
    receiptName.textContent = receiptFile ? receiptFile.name : 'Chưa chọn biên nhận';
    filesList.hidden = files.length === 0;
    filesList.innerHTML = files.map((f, index) => `
      <li class="file-list__item">
        <span class="file-list__name">
          <i data-lucide="${EC.fileType(f.name).icon}"></i>
          <span class="file-list__filename">${EC.escape(f.name)}</span>
          <span class="file-list__size">(${EC.formatSize(f.size)})</span>
        </span>
        <button type="button" class="icon-btn" data-remove="${index}" title="Bỏ file" aria-label="Bỏ ${EC.escape(f.name)}">
          <i data-lucide="x" class="icon-sm"></i>
        </button>
      </li>`).join('');
    verifyButton.disabled = !receiptFile || files.length === 0;
    EC.refreshIcons();
  }

  receiptInput.addEventListener('change', () => {
    receiptFile = receiptInput.files[0] || null;
    resultBox.hidden = true;
    render();
  });

  filesInput.addEventListener('change', () => {
    Array.from(filesInput.files).forEach((file) => {
      if (!files.some((f) => f.name === file.name && f.size === file.size)) files.push(file);
    });
    filesInput.value = '';
    resultBox.hidden = true;
    render();
  });

  filesList.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-remove]');
    if (!btn) return;
    files.splice(Number(btn.dataset.remove), 1);
    render();
  });

  function showResult(body) {
    resultBox.hidden = false;
    summary.className = `alert ${body.valid ? 'alert--success' : 'alert--danger'}`;
    summary.innerHTML = body.valid
      ? `<i data-lucide="circle-check" class="icon-sm"></i><p><strong>Biên nhận ${EC.escape(body.receiptCode)} hợp lệ.</strong>
         File khớp bản đã lưu chứng, biên nhận đúng chữ ký hệ thống và đã ghi lên chuỗi công khai.</p>`
      : `<i data-lucide="circle-x" class="icon-sm"></i><p><strong>Biên nhận ${EC.escape(body.receiptCode || '')} không hợp lệ.</strong>
         Xem bước không đạt bên dưới. Kết quả không kết luận ai đã sửa (nén, chuyển mã file cũng ra kết quả này).</p>`;
    checksList.innerHTML = body.checks.map((c) => `
      <li class="verify-receipt__check">
        ${EC.badge(c.ok ? 'checkPass' : 'checkFail')}
        <span>${EC.escape(c.name)}${c.detail ? ` <span class="text-secondary">— ${EC.escape(c.detail)}</span>` : ''}</span>
      </li>`).join('');
    EC.refreshIcons();
  }

  verifyButton.addEventListener('click', async () => {
    verifyButton.disabled = true;
    verifyLabel.textContent = 'Đang kiểm tra…';
    try {
      showResult(await EC.data.verifyReceipt(receiptFile, files));
    } catch (err) {
      resultBox.hidden = false;
      summary.className = 'alert alert--danger';
      summary.innerHTML = `<i data-lucide="circle-alert" class="icon-sm"></i><p>${EC.escape(err.message)}</p>`;
      checksList.innerHTML = '';
      EC.refreshIcons();
    } finally {
      verifyLabel.textContent = 'Kiểm tra';
      render();
    }
  });

  render();
})(window.EC);
