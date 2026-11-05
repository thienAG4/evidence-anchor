/* ==========================================================================
   OpenTimestamps trong trình duyệt (tài liệu kỹ thuật 6.9): đương sự tự đóng dấu hash file lên Bitcoin.

   Hash file do server tính (phương án B) và trả trong biên nhận. Trình duyệt trộn thêm nonce 16 byte ngẫu nhiên,
   băm lại, gửi giá trị đó tới từng máy chủ lịch: máy chủ lịch không thấy file, cũng không thấy hash file.
   Máy chủ lịch chặn CORS thì gửi qua máy chủ Tòa chuyển tiếp (POST /ots/relay/{i}); Tòa cũng chỉ thấy giá trị
   đã trộn nonce. File .ots ghép theo định dạng chuẩn (đọc được bằng `ots info`, `ots verify`, opentimestamps.org):
     magic ‖ version 1 ‖ 0x08 (SHA256) ‖ fileHash ‖ các nhánh, mỗi máy chủ lịch một nhánh:
       0xf0 (append) ‖ 16 ‖ nonce ‖ 0x08 (sha256) ‖ phản hồi của máy chủ lịch
     nhánh không phải cuối có tiền tố 0xff.
   ========================================================================== */

(function (EC) {
  'use strict';

  // Cùng thứ tự với OTS_CALENDARS của server (chỉ số dùng cho đường chuyển tiếp)
  const CALENDARS = ['https://a.pool.opentimestamps.org', 'https://b.pool.opentimestamps.org',
    'https://a.pool.eternitywall.com', 'https://ots.btc.catallaxy.com'];
  const MAGIC = '004f70656e54696d657374616d7073000050726f6f6600bf89e2e884e89294';

  const hex = (s) => Uint8Array.from(s.match(/../g), (b) => parseInt(b, 16));
  const concat = (...parts) => {
    const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
    let i = 0;
    parts.forEach((p) => { out.set(p, i); i += p.length; });
    return out;
  };
  const sha256 = async (bytes) => new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));

  async function submit(index, digest) {
    try { // gọi thẳng: body nhị phân, không header riêng -> trình duyệt không gửi preflight
      const r = await fetch(`${CALENDARS[index]}/digest`, { method: 'POST', body: digest });
      if (r.ok) return { bytes: new Uint8Array(await r.arrayBuffer()), via: 'direct' };
    } catch (e) { /* CORS hoặc mạng: thử qua máy chủ Tòa */ }
    const r = await fetch(`${EC.API_BASE}/ots/relay/${index}`, {
      method: 'POST', body: digest, headers: { Authorization: `Bearer ${EC.auth.token()}` },
    });
    if (!r.ok) throw new Error(`máy chủ lịch ${index} không nhận`);
    return { bytes: new Uint8Array(await r.arrayBuffer()), via: 'relay' };
  }

  /** Đóng dấu một hash file (hex). Trả { ots: Uint8Array, direct: n, relay: n }. Không máy chủ lịch nào nhận -> lỗi. */
  async function stamp(fileHashHex) {
    const fileHash = hex(fileHashHex);
    const results = await Promise.all(CALENDARS.map(async (_, i) => {
      const nonce = crypto.getRandomValues(new Uint8Array(16));
      try {
        const answer = await submit(i, await sha256(concat(fileHash, nonce)));
        return { branch: concat(Uint8Array.of(0xf0, 16), nonce, Uint8Array.of(0x08), answer.bytes), via: answer.via };
      } catch (e) {
        return null;
      }
    }));
    const ok = results.filter(Boolean);
    if (!ok.length) throw new Error('Không máy chủ lịch OpenTimestamps nào nhận. Kiểm tra mạng rồi thử lại.');
    const branches = ok.map((r, i) => (i < ok.length - 1 ? concat(Uint8Array.of(0xff), r.branch) : r.branch));
    return {
      ots: concat(hex(MAGIC), Uint8Array.of(0x01, 0x08), fileHash, ...branches),
      direct: ok.filter((r) => r.via === 'direct').length,
      relay: ok.filter((r) => r.via === 'relay').length,
    };
  }

  /** Lưu file về máy đương sự (giữ bản chờ riêng, 6.9) */
  function save(bytes, name) {
    const link = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' })), download: name,
    });
    link.click();
    URL.revokeObjectURL(link.href);
  }

  /**
   * Đóng dấu mọi file chưa có dấu của một biên nhận, gửi bản chờ lên server. files: [{ code, hash }].
   * Trả [{ code, ok, error? }]. Gọi ngay sau khi lưu chứng, hoặc từ nút trên trang chi tiết biên nhận.
   */
  async function stampReceipt(receiptId, files) {
    return Promise.all(files.map(async (f) => {
      try {
        const { ots } = await stamp(f.hash);
        const form = new FormData();
        form.append('fileCode', f.code);
        form.append('ots', new Blob([ots]), `${f.code}.ots`);
        await EC.api(`/receipts/${encodeURIComponent(receiptId)}/ots`, { method: 'POST', form });
        return { code: f.code, ok: true };
      } catch (e) {
        return { code: f.code, ok: e.code === 'OTS_EXISTS', error: e.message };
      }
    }));
  }

  EC.ots = { stamp, stampReceipt, save, CALENDARS };
})(window.EC);
