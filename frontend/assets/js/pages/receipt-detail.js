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
        time: isLocked ? receipt.lockedAt : EC.lockPendingText(receipt), // chưa khóa: không hiện giờ (UI-11)
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

  // ---------------------------------------------------------------- Neo ngay (chỉ khi còn chờ neo)
  if (receipt.status === 'recorded') {
    const box = document.getElementById('receipt-anchor-now');
    const hint = document.getElementById('receipt-anchor-hint');
    const button = document.getElementById('receipt-anchor-button');
    const showSchedule = (s) => {
      if (s.halted) {
        hint.textContent = 'Job neo đang tạm dừng để người vận hành kiểm tra. Bản ghi vẫn được giữ, sẽ neo khi chạy lại.';
        button.disabled = true;
      } else if (s.requestedAt) {
        hint.textContent = 'Đã gửi yêu cầu neo ngay. Hệ thống sẽ đưa bản ghi lên blockchain trong ít giây.';
        button.disabled = true;
      } else if (s.mode === 'daily' && s.nextLockAt) {
        hint.textContent = `Hệ thống tự khóa lúc ${EC.data.vnTime(s.nextLockAt)}. Bấm "Neo ngay" để khóa sớm.`;
      } else {
        hint.textContent = 'Hệ thống đang đưa bản ghi lên blockchain.';
      }
    };
    EC.api('/anchor/schedule', { auth: false }).then((s) => { box.hidden = false; showSchedule(s); }).catch(() => {});
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        showSchedule(await EC.api('/anchor/now', { method: 'POST' }));
      } catch (err) {
        alert(`Không gửi được yêu cầu: ${err.message}`);
        button.disabled = false;
      }
    });
  }

  // ---------------------------------------------------------------- Tự cập nhật trạng thái neo
  // Worker gửi giao dịch ngay khi có bản ghi: Chờ neo -> Đã neo, chờ chốt (vài giây) -> Đã khóa (block chốt, ~13 phút).
  // Trạng thái đổi thì tải lại trang để hiện bước mới; đã khóa thì thôi theo dõi.
  if (!EC.isLocked(receipt)) {
    let firstStatus = null;
    const check = async () => {
      const detail = await EC.api(`/receipts/${encodeURIComponent(receipt.id)}`).catch(() => null);
      if (!detail) return;
      if (firstStatus === null) firstStatus = detail.view.status;
      else if (detail.view.status !== firstStatus) { clearInterval(watch); location.reload(); }
    };
    const watch = setInterval(check, 5000);
    check();
  }

  // ---------------------------------------------------------------- OpenTimestamps (6.9)
  const otsBox = document.getElementById('receipt-ots');
  const otsNote = document.getElementById('receipt-ots-note');
  const otsList = document.getElementById('receipt-ots-list');
  const b64bytes = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

  function renderOts(items) {
    const byCode = Object.fromEntries(items.map((i) => [i.fileCode, i]));
    otsList.innerHTML = files.map((f) => {
      const it = byCode[f.code];
      const state = !it ? 'Chưa đóng dấu'
        : (it.status === 'COMPLETE' ? `Đã có trên Bitcoin, block ${it.bitcoinBlock}` : 'Đã đóng dấu, chờ Bitcoin xác nhận (vài giờ)');
      return `<li><span><span class="code-text">${EC.escape(f.code)}</span> · ${EC.escape(state)}</span>
        ${it ? `<button type="button" class="btn btn--secondary" data-ots="${EC.escape(f.code)}">
          <i data-lucide="download" class="icon-sm"></i>Tải ${EC.escape(f.code)}.ots</button>` : ''}</li>`;
    }).join('');
    otsList.querySelectorAll('[data-ots]').forEach((btn) => btn.addEventListener('click', () => {
      EC.ots.save(b64bytes(byCode[btn.dataset.ots].ots), `${btn.dataset.ots}.ots`);
    }));
    if (window.lucide) window.lucide.createIcons();
  }

  async function loadOts() {
    const body = await EC.api(`/receipts/${encodeURIComponent(receipt.id)}`);
    otsBox.hidden = false;
    renderOts(body.ots);
    const missing = files.filter((f) => f.hash && !body.ots.some((i) => i.fileCode === f.code));
    if (!missing.length) {
      otsNote.textContent = body.ots.every((i) => i.status === 'COMPLETE')
        ? 'Mọi file đã có dấu thời gian trên Bitcoin. Tải lại biên nhận (.json) để có bản hoàn chỉnh.'
        : 'Hệ thống tự nâng cấp mỗi giờ. Khi Bitcoin xác nhận, tải lại file .ots hoặc biên nhận (.json).';
      return;
    }
    otsNote.textContent = `Đang đóng dấu ${missing.length} file lên Bitcoin...`;
    const results = await EC.ots.stampReceipt(receipt.id, missing);
    const failed = results.filter((r) => !r.ok);
    renderOts((await EC.api(`/receipts/${encodeURIComponent(receipt.id)}`)).ots);
    otsNote.textContent = failed.length
      ? `Chưa đóng dấu được ${failed.map((r) => r.code).join(', ')}: ${failed[0].error}. Mở lại trang để thử lại.`
      : 'Đã đóng dấu. Bitcoin xác nhận sau vài giờ; hệ thống tự nâng cấp mỗi giờ. Nên tải file .ots về giữ riêng.';
  }
  if (EC.ots) loadOts().catch(() => {});

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

  // ---------------------------------------------------------------- Tải biên nhận (UI-16)
  const downloadButton = document.getElementById('receipt-download');
  const downloadNote = document.getElementById('receipt-download-note');
  if (!EC.isLocked(receipt)) { // gồm 'anchoring': đã neo nhưng block chưa chốt, biên nhận chưa có phần anchor
    downloadNote.hidden = false;
    downloadNote.textContent = 'Biên nhận chưa khóa nên chưa có bằng chứng neo. Bạn vẫn tải được bản tạm (có chữ ký hệ thống); '
      + 'hãy tải lại sau khi trạng thái là "Đã khóa" để có biên nhận hoàn chỉnh.';
  }
  downloadButton.addEventListener('click', async () => {
    downloadButton.disabled = true;
    try {
      const complete = await EC.data.downloadReceipt(receipt.id);
      downloadNote.hidden = false;
      downloadNote.textContent = complete
        ? `Đã tải biên nhận hoàn chỉnh bien-nhan-${receipt.id}.json (có bằng chứng neo). Giữ file này cùng file gốc.`
        : `Đã tải biên nhận tạm bien-nhan-${receipt.id}.json. Tải lại sau khi khóa để có bằng chứng neo.`;
    } catch (err) {
      alert(`Không tải được biên nhận: ${err.message}`);
    } finally {
      downloadButton.disabled = false;
    }
  });
  });
})(window.EC);
