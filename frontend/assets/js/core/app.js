/* ==========================================================================
   app.js – nạp ĐẦU TIÊN trên mọi trang.
   Tạo namespace toàn cục `EC` (EvidenceChain) và các hàm tiện ích dùng chung.
   Dùng <script defer> thường (không dùng ES module) để mở được cả khi
   bấm đúp file .html (file://) lẫn khi chạy bằng Live Server.
   ========================================================================== */

window.EC = window.EC || {};

(function (EC) {
  'use strict';

  // Thư mục gốc frontend/ — suy ra từ vị trí file này: assets/js/core/app.js
  const ROOT_URL = new URL('../../../', document.currentScript.src);

  /** Đường dẫn tuyệt đối tới một file trong frontend/, vd EC.url('pages/auth/login.html') */
  EC.url = function (path) {
    return new URL(path, ROOT_URL).href;
  };

  /** Lấy tham số trên URL, vd ?id=TX-0007 → EC.param('id') */
  EC.param = function (name) {
    return new URLSearchParams(window.location.search).get(name);
  };

  /** Chống chèn HTML khi đưa dữ liệu vào template string */
  EC.escape = function (value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  /** Chuẩn hóa chuỗi để tìm kiếm không phân biệt hoa/thường và dấu: "Trần" → "tran" */
  EC.normalize = function (value) {
    return String(value ?? '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/đ/g, 'd')
      .replace(/Đ/g, 'D')
      .toLowerCase()
      .trim();
  };

  /** "HH:mm dd/MM/yyyy" hoặc "dd/MM/yyyy" → Date (để lọc theo ngày) */
  EC.parseDate = function (text) {
    const m = String(text).match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    return m ? new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1])) : null;
  };

  /** Vẽ lại icon Lucide sau khi chèn HTML mới có <i data-lucide="…"> */
  EC.refreshIcons = function () {
    if (window.lucide) {
      window.lucide.createIcons({ attrs: { 'stroke-width': 1.5 } });
    }
  };

  /** Định dạng dung lượng file kiểu Việt Nam: 2,4 MB / 860 KB */
  EC.formatSize = function (bytes) {
    if (bytes >= 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(1).replace('.', ',') + ' MB';
    }
    return Math.max(1, Math.round(bytes / 1024)) + ' KB';
  };

  /** Thời điểm hiện tại dạng "HH:mm dd/MM/yyyy" */
  EC.nowText = function () {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
  };

  /**
   * Tính SHA-256 của một File ngay trên trình duyệt (file không gửi đi đâu).
   * Trả về chuỗi hex 64 ký tự, hoặc null nếu trình duyệt không hỗ trợ.
   */
  EC.sha256 = async function (file) {
    if (!window.crypto || !window.crypto.subtle) return null;
    const buffer = await file.arrayBuffer();
    const digest = await window.crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  };

  /** Rút gọn hash ở giữa: a3f9…c21e */
  EC.shortHash = function (hash) {
    return hash ? `${hash.slice(0, 6)}…${hash.slice(-6)}` : '';
  };

  /** Icon theo loại file (dựa trên đuôi file) */
  EC.fileType = function (fileName) {
    const ext = String(fileName).split('.').pop().toLowerCase();
    if (ext === 'pdf' || ext === 'doc' || ext === 'docx') return { type: 'pdf', icon: 'file-text' };
    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'heic'].includes(ext)) return { type: 'image', icon: 'image' };
    if (['mp3', 'm4a', 'wav', 'aac', 'ogg'].includes(ext)) return { type: 'audio', icon: 'music' };
    if (['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext)) return { type: 'video', icon: 'video' };
    return { type: 'other', icon: 'file' };
  };

  /** HTML tên file kèm icon */
  EC.fileNameHtml = function (fileName) {
    const t = EC.fileType(fileName);
    return `<span class="file-name file-name--${t.type}"><i data-lucide="${t.icon}"></i>${EC.escape(fileName)}</span>`;
  };

  // Sau khi mọi script defer đã chạy xong → vẽ toàn bộ icon trên trang
  document.addEventListener('DOMContentLoaded', EC.refreshIcons);
})(window.EC);
