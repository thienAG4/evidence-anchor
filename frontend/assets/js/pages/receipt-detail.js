/* ==========================================================================
   Trang Chi tiết biên nhận – pages/litigant/receipt-detail.html?id=TX-0007
   Một trang dùng cho mọi biên nhận; nội dung lấy theo ?id= từ API (GET /receipts/{id}, chỉ biên nhận của mình).
   ========================================================================== */

(function (EC) {
  'use strict';
  EC.data.whenReady(() => {

  const receipt = EC.data.getReceipt(EC.param('id') || '');

  function setField(name, value) {
    document.querySelectorAll(`[data-field="${name}"]`).forEach((el) => { el.textContent = value; });
  }

  if (!receipt) {
    document.getElementById('receipt-content').hidden = true;
    document.getElementById('receipt-not-found').hidden = false;
    setField('id', EC.param('id') || '');
    return;
  }

  const files = receipt.files;
  document.title = `Biên nhận ${receipt.id} – EvidenceChain`;

  // ---------------------------------------------------------------- Thông tin
  setField('id', receipt.id);
  setField('subtitle', `Lưu chứng lúc ${receipt.recordedAt} · ${files.length} file`);
  setField('recordedAt', receipt.recordedAt);
  setField('litigant', receipt.litigant);
  setField('fileCount', files.length);

  // ---------------------------------------------------------------- Stepper
  function buildSteps() {
    const isLocked = EC.isLocked(receipt);
    const checkedCount = files.filter((f) => f.result === 'match' || f.result === 'mismatch').length;
    const inProgress = files.some((f) => f.result === 'checking');

    let courtStep;
    if (checkedCount === files.length) {
      courtStep = { state: 'done', time: `Đã kiểm tra ${checkedCount}/${files.length} file` };
    } else if (checkedCount > 0 || inProgress) {
      courtStep = { state: 'current', time: `Đã kiểm tra ${checkedCount}/${files.length} file` };
    } else {
      courtStep = { state: 'pending', time: 'Chưa kiểm tra' };
    }

    return [
      { label: 'Đã ghi nhận', state: 'done', time: receipt.recordedAt },
      {
        label: 'Đã khóa, không thể sửa',
        state: isLocked ? 'done' : 'current',
        time: isLocked ? receipt.lockedAt : EC.lockPendingText(receipt),
      },
      { label: 'Tòa đã kiểm tra', state: isLocked ? courtStep.state : 'pending', time: isLocked ? courtStep.time : 'Chưa kiểm tra' },
    ];
  }

  const STEP_ICON = { done: 'check', current: 'clock', pending: 'file-search' };

  document.getElementById('receipt-stepper').innerHTML = buildSteps().map((s) => `
    <li class="stepper__step is-${s.state}">
      <span class="stepper__icon"><i data-lucide="${STEP_ICON[s.state]}"></i></span>
      <span class="stepper__label">${EC.escape(s.label)}</span>
      <span class="stepper__time">${EC.escape(s.time)}</span>
    </li>`).join('');

  // ---------------------------------------------------------------- Bảng mã file
  document.getElementById('receipt-files-body').innerHTML = files.map((f) => `
    <tr>
      <td class="code-text">${EC.escape(f.code)}</td>
      <td>${EC.fileNameHtml(f.name)}</td>
      <td>${EC.badge(f.result, { withHint: true })}</td>
      <td class="text-secondary">${f.checkedAt ? EC.escape(f.checkedAt) : '—'}</td>
    </tr>`).join('');

  // Chỉ hiện chú thích khi Tòa đã bắt đầu kiểm tra
  document.getElementById('receipt-legend').hidden = files.every((f) => f.result === 'unchecked');

  // ---------------------------------------------------------------- Thông tin kỹ thuật
  const hashed = files.filter((f) => f.hash);
  if (hashed.length) {
    document.getElementById('receipt-tech').hidden = false;
    document.getElementById('receipt-tech-list').innerHTML = hashed.map((f) => `
      <li><span class="code-text">${EC.escape(f.code)}</span><span class="mono" title="${f.hash}">${f.hash}</span></li>`).join('');
  }
  });
})(window.EC);
