/* ==========================================================================
   Trang Lưu chứng cứ – pages/litigant/submit-evidence.html
   - Chọn / kéo thả file, xóa từng file khỏi danh sách.
   - "Lưu chứng cứ": gửi file lên POST /submissions; máy chủ băm từng file (kèm giờ) rồi bỏ file,
     trả biên nhận. Chỉ nhận PDF, ảnh, video, âm thanh.
   Xem trước trạng thái: ?state=success | ?state=error
   ========================================================================== */

(function (EC) {
  'use strict';
  EC.data.whenReady(() => {

  const CURRENT_USER = EC.USERS.litigant;

  // File mẫu CHỈ dùng khi xem trước trạng thái (?state=success|error), không có nội dung thật
  const SAMPLE_FILES = [
    { name: 'hop_dong_vay.pdf', size: 2.4 * 1024 * 1024 },
    { name: 'anh_chuyen_khoan.png', size: 860 * 1024 },
    { name: 'ghi_am_cuoc_goi.m4a', size: 5.1 * 1024 * 1024 },
  ];

  const picker = document.getElementById('file-picker');
  const fileInput = document.getElementById('file-input');
  const fileList = document.getElementById('file-list');
  const submitButton = document.getElementById('submit-button');
  const submitLabel = document.getElementById('submit-label');
  const tableBody = document.getElementById('receipt-table-body');

  /** Mỗi phần tử: { name, size, file? } — `file` là File thật nếu người dùng chọn */
  const previewState = EC.param('state');
  // Mới vào trang: chưa có file nào. Chỉ điền file mẫu khi xem trước trạng thái.
  let selectedFiles = previewState ? SAMPLE_FILES.map((f) => ({ ...f })) : [];
  let forceError = previewState === 'error';

  // ---------------------------------------------------------------- Render
  function renderFileList() {
    fileList.hidden = selectedFiles.length === 0;
    fileList.innerHTML = selectedFiles.map((f, index) => {
      const type = EC.fileType(f.name);
      return `
        <li class="file-list__item">
          <span class="file-list__name">
            <i data-lucide="${type.icon}"></i>
            <span class="file-list__filename">${EC.escape(f.name)}</span>
            <span class="file-list__size">(${EC.formatSize(f.size)})</span>
          </span>
          <button type="button" class="icon-btn" data-remove="${index}" title="Xóa file" aria-label="Xóa ${EC.escape(f.name)}">
            <i data-lucide="x" class="icon-sm"></i>
          </button>
        </li>`;
    }).join('');

    const count = selectedFiles.length;
    submitButton.disabled = count === 0;
    submitLabel.textContent = count ? `Lưu chứng cứ ${count} file` : 'Lưu chứng cứ';
    EC.refreshIcons();
  }

  function renderReceiptTable() {
    const rows = EC.data.receiptsOf(CURRENT_USER.name);
    tableBody.innerHTML = rows.map((r) => `
      <tr data-href="receipt-detail.html?id=${encodeURIComponent(r.id)}">
        <td>${EC.escape(r.id)}</td>
        <td class="is-center">${r.files.length}</td>
        <td class="is-nowrap">${EC.escape(r.recordedAt)}</td>
        <td>${EC.badge(r.status, { withHint: true })}</td>
        <td class="is-right">
          <a class="link link--arrow" href="receipt-detail.html?id=${encodeURIComponent(r.id)}">
            Xem chi tiết <i data-lucide="chevron-right" class="icon-sm"></i>
          </a>
        </td>
      </tr>`).join('');
    EC.refreshIcons();
  }

  // ---------------------------------------------------------------- Chọn file
  function addFiles(files) {
    Array.from(files).forEach((file) => {
      const duplicate = selectedFiles.some((f) => f.name === file.name && f.size === file.size);
      if (!duplicate) selectedFiles.push({ name: file.name, size: file.size, file });
    });
    renderFileList();
  }

  // Chọn file thật → bỏ các file mẫu (nếu đang xem trước trạng thái)
  function dropSampleFiles() {
    selectedFiles = selectedFiles.filter((f) => f.file);
  }

  fileInput.addEventListener('change', () => {
    dropSampleFiles();
    addFiles(fileInput.files);
    fileInput.value = '';
  });

  fileList.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-remove]');
    if (!btn) return;
    selectedFiles.splice(Number(btn.dataset.remove), 1);
    renderFileList();
  });

  // Kéo thả file vào khung chọn
  ['dragenter', 'dragover'].forEach((type) => picker.addEventListener(type, (e) => {
    e.preventDefault();
    picker.classList.add('is-dragover');
  }));
  ['dragleave', 'drop'].forEach((type) => picker.addEventListener(type, (e) => {
    e.preventDefault();
    picker.classList.remove('is-dragover');
  }));
  picker.addEventListener('drop', (e) => {
    dropSampleFiles();
    addFiles(e.dataTransfer.files);
  });

  // Bấm cả hàng trong bảng để mở chi tiết
  tableBody.addEventListener('click', (event) => {
    const row = event.target.closest('tr[data-href]');
    if (row && !event.target.closest('a')) window.location.href = row.dataset.href;
  });

  // ---------------------------------------------------------------- Lưu chứng
  const errorText = document.querySelector('#modal-submit-error .modal__text');
  const DEFAULT_ERROR = errorText.textContent;

  async function submitEvidence() {
    submitButton.disabled = true;
    submitLabel.textContent = 'Đang gửi và tính mã băm…';

    try {
      if (forceError) throw new Error(DEFAULT_ERROR);
      const files = selectedFiles.filter((f) => f.file).map((f) => f.file);
      if (!files.length) throw new Error('Hãy chọn file thật trên máy (file mẫu chỉ để xem trước giao diện).');

      const receipt = await EC.data.submit(files);
      showSuccess(receipt);
      selectedFiles = [];
      renderReceiptTable();
    } catch (err) {
      // Lỗi từ máy chủ đã có câu tiếng Việt, ví dụ file .exe/.zip bị từ chối, mất kết nối
      errorText.textContent = `${err.message} Chưa có lần lưu chứng cứ nào được tạo.`;
      EC.modal.open('modal-submit-error');
    } finally {
      renderFileList();
    }
  }

  function showSuccess(receipt) {
    const modal = document.getElementById('modal-submit-success');
    modal.querySelectorAll('[data-field="id"]').forEach((el) => { el.textContent = receipt.id; });
    modal.querySelectorAll('[data-field="recordedAt"]').forEach((el) => { el.textContent = receipt.recordedAt; });
    modal.querySelectorAll('[data-field="count"]').forEach((el) => { el.textContent = receipt.files.length; });
    modal.querySelector('[data-field="status"]').innerHTML = EC.badge(receipt.status);
    document.getElementById('success-detail-link').href = `receipt-detail.html?id=${encodeURIComponent(receipt.id)}`;
    EC.refreshIcons();
    EC.modal.open('modal-submit-success');
  }

  submitButton.addEventListener('click', submitEvidence);

  document.getElementById('retry-button').addEventListener('click', () => {
    EC.modal.close('modal-submit-error');
    forceError = false; // lần thử lại trong bản demo sẽ thành công
    submitEvidence();
  });

  // ---------------------------------------------------------------- Khởi tạo
  renderFileList();
  renderReceiptTable();

  if (previewState === 'success') {
    showSuccess({
      id: EC.data.nextReceiptId(),
      recordedAt: EC.nowText(),
      status: 'recorded',
      files: selectedFiles,
    });
  } else if (forceError) {
    EC.modal.open('modal-submit-error');
  }
  });
})(window.EC);
