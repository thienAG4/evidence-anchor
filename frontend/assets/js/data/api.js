/* ==========================================================================
   api.js – nối giao diện với backend FastAPI (thay cho mock-data.js).
   - EC.api(path, …): gọi API, tự gắn token, lỗi trả về EC.ApiError (message tiếng Việt từ server).
   - EC.auth: đăng nhập, lưu token + người dùng, kiểm tra quyền vào trang.
   - EC.data: giữ nguyên các hàm trang đang dùng (receipts, getReceipt, receiptsOf…) nhưng dữ liệu lấy từ API.
     Trang vẽ trong EC.data.whenReady(() => { … }) để chờ dữ liệu tải xong.
   Nạp SAU navigation.js, status.js và TRƯỚC các component header/sidebar.
   ========================================================================== */

(function (EC) {
  'use strict';

  const TOKEN_KEY = 'evidencechain.token';
  const USER_KEY = 'evidencechain.user';
  const ROLE_OF = { PARTY: 'litigant', CLERK: 'clerk' }; // vai trò backend → vai trò giao diện
  const RESULT_OF = { UNCHANGED: 'match', CHANGED: 'mismatch', NO_BASELINE: 'noBaseline' };

  // Mở qua backend (http://localhost:8000) → gọi cùng origin. Mở file trực tiếp hoặc Live Server → gọi :8000.
  EC.API_BASE = window.EC_API_BASE
    ?? (location.protocol === 'file:' || location.port === '5500' ? 'http://localhost:8000' : '');

  const storage = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* trình duyệt chặn */ } },
    remove(key) { try { localStorage.removeItem(key); } catch (e) { /* bỏ qua */ } },
  };

  class ApiError extends Error {
    constructor(message, code, status) {
      super(message);
      this.code = code;
      this.status = status;
    }
  }
  EC.ApiError = ApiError;

  function goToLogin() {
    if (!location.pathname.endsWith(EC.LOGIN_PAGE)) location.replace(EC.url(EC.LOGIN_PAGE));
  }

  /**
   * Gọi API. options: { method, json, form (FormData), auth=true }.
   * Trả về JSON; lỗi ném EC.ApiError. Token hết hạn (401) → xóa phiên, về trang đăng nhập.
   */
  EC.api = async function (path, { method = 'GET', json, form, auth = true } = {}) {
    const headers = {};
    const token = EC.auth.token();
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    let body;
    if (json !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(json);
    } else if (form) {
      body = form; // trình duyệt tự đặt multipart boundary
    }

    let response;
    try {
      response = await fetch(EC.API_BASE + path, { method, headers, body });
    } catch (e) {
      throw new ApiError('Không kết nối được máy chủ EvidenceChain. Kiểm tra server đã chạy chưa.', 'NETWORK', 0);
    }
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const error = (data && data.error) || {};
      if (response.status === 401 && auth) {
        EC.auth.clear();
        goToLogin();
      }
      throw new ApiError(error.message || `Máy chủ báo lỗi ${response.status}.`, error.code, response.status);
    }
    return data;
  };

  // ---------------------------------------------------------------- Đăng nhập
  EC.auth = {
    token() { return storage.get(TOKEN_KEY); },
    user() {
      try { return JSON.parse(storage.get(USER_KEY)); } catch (e) { return null; }
    },
    /** 'litigant' | 'clerk' | null */
    role() {
      const user = this.user();
      return user ? ROLE_OF[user.role] || null : null;
    },
    clear() {
      storage.remove(TOKEN_KEY);
      storage.remove(USER_KEY);
    },
    /** Đăng nhập; trả về vai trò giao diện. Vai trò chưa có giao diện (thẩm phán, admin) → báo lỗi. */
    async login(username, password) {
      const body = await EC.api('/auth/login', { method: 'POST', json: { username, password }, auth: false });
      const role = ROLE_OF[body.user.role];
      if (!role) {
        throw new ApiError(`Tài khoản vai trò ${body.user.role} chưa có giao diện web. Hãy dùng API (/docs).`,
          'UNSUPPORTED_ROLE', 403);
      }
      storage.set(TOKEN_KEY, body.token);
      storage.set(USER_KEY, JSON.stringify(body.user));
      return role;
    },
  };

  // Tên người dùng trên header lấy từ tài khoản đang đăng nhập
  const currentRole = EC.auth.role();
  if (currentRole && EC.USERS[currentRole]) {
    EC.USERS[currentRole] = { ...EC.USERS[currentRole], name: EC.auth.user().fullName };
  }

  // Trang cần đăng nhập (<app-header role="…">): chưa đăng nhập → về đăng nhập; sai vai trò → về trang của mình
  const pageRole = document.querySelector('app-header[role]')?.getAttribute('role');
  const blocked = pageRole && (!EC.auth.token() || currentRole !== pageRole);
  if (blocked) {
    if (!EC.auth.token() || !currentRole) goToLogin();
    else location.replace(EC.url(EC.HOME_PAGE[currentRole]));
  }

  // ---------------------------------------------------------------- Chuyển dữ liệu API → dạng trang dùng
  /** "2026-11-04T13:12:47.55+07:00" → "13:12 04/11/2026" (giờ VN do server ghi, không đổi múi giờ) */
  function vnText(iso) {
    const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    return m ? `${m[4]}:${m[5]} ${m[3]}/${m[2]}/${m[1]}` : '—';
  }

  /**
   * Biên nhận từ API → { id, litigant, status, recordedAt, lockedAt, files: [{ code, name, hash, result, checkedAt }] }.
   * status: recorded (chưa neo lên chuỗi) → locked (đã neo, không ai sửa được) → checked (Tòa đã đối chiếu).
   */
  function toReceipt(view) {
    const day = vnText(view.submittedAt).split(' ')[1];
    return {
      id: view.receiptCode,
      litigant: view.owner.fullName,
      status: view.status !== 'ANCHORED' ? 'recorded' : (view.checked ? 'checked' : 'locked'),
      anchorStatus: view.status,
      recordedAt: vnText(view.submittedAt),
      lockedAt: view.anchoredAt ? vnText(view.anchoredAt) : `23:59 ${day}`,
      files: view.files.map((f) => ({
        code: f.fileCode,
        name: f.fileName,
        hash: f.fileHash || null, // chỉ có khi đương sự xem biên nhận của chính mình
        result: f.result ? RESULT_OF[f.result.value] : 'unchecked',
        checkedAt: f.result ? vnText(f.result.checkedAt) : null,
        phase: f.phase,
      })),
    };
  }

  const receipts = [];
  const litigants = [];

  function upsert(receipt) {
    const index = receipts.findIndex((r) => r.id === receipt.id);
    if (index >= 0) receipts[index] = receipt;
    else receipts.unshift(receipt);
    return receipt;
  }

  async function load() {
    if (currentRole === 'litigant') {
      const list = await EC.api('/submissions?size=100');
      receipts.push(...list.items.map(toReceipt));
      const id = EC.param('id');
      if (id) { // trang chi tiết: lấy bản đầy đủ (có mã băm để tự kiểm tra)
        try {
          upsert(toReceipt((await EC.api(`/receipts/${encodeURIComponent(id)}`)).view));
        } catch (e) {
          if (e.status !== 404) throw e;
        }
      }
    } else if (currentRole === 'clerk') {
      const [list, people] = await Promise.all([EC.api('/clerk/receipts'), EC.api('/clerk/litigants')]);
      receipts.push(...list.items.map(toReceipt));
      litigants.push(...people.items.map((p) => ({ name: p.fullName, username: p.username, email: p.email })));
    }
  }

  /** Hiện thông báo lỗi ở đầu nội dung trang */
  EC.showPageError = function (message) {
    const main = document.querySelector('.app-main') || document.body;
    const box = document.createElement('div');
    box.className = 'alert alert--danger';
    box.setAttribute('role', 'alert');
    box.innerHTML = `<i data-lucide="circle-alert" class="icon-sm"></i><p>${EC.escape(message)}</p>`;
    main.prepend(box);
    EC.refreshIcons();
  };

  const ready = blocked || !currentRole
    ? Promise.resolve(false)
    : load().then(() => true, (err) => {
      EC.showPageError(err.message);
      return false;
    });

  EC.data = {
    receipts,
    litigants,

    /** Các giai đoạn tố tụng khi đối chiếu */
    verifyPhases: [
      'Phiên họp kiểm tra chứng cứ',
      'Trước khi gửi giám định',
      'Phiên tòa sơ thẩm',
      'Phiên tòa phúc thẩm',
    ],

    /** Chạy fn khi dữ liệu đã tải xong (không chạy nếu tải lỗi hoặc đang chuyển trang) */
    whenReady(fn) {
      return ready.then((ok) => (ok ? fn() : undefined));
    },

    getReceipt(id) {
      return receipts.find((r) => r.id === id) || null;
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
        lastAt: list.length ? list[0].recordedAt : '—', // API trả mới nhất trước
      };
    },

    /** Chỉ để xem trước giao diện (?state=success) */
    nextReceiptId() {
      return 'TX-…';
    },

    /** Đương sự lưu chứng: gửi file lên server băm (băm xong bỏ file), nhận biên nhận */
    async submit(files) {
      const form = new FormData();
      files.forEach((file) => form.append('files', file, file.name));
      const created = await EC.api('/submissions', { method: 'POST', form });
      const detail = await EC.api(`/receipts/${encodeURIComponent(created.receiptCode)}`);
      return upsert(toReceipt(detail.view));
    },

    /** Thư ký xem trước: so 1 file trong hồ sơ Tòa với file cùng mã. Trả 'match' | 'mismatch', không ghi */
    async compare(receiptId, fileCode, file) {
      const form = new FormData();
      form.append('fileCode', fileCode);
      form.append('file', file, file.name);
      const body = await EC.api(`/clerk/receipts/${encodeURIComponent(receiptId)}/compare`, { method: 'POST', form });
      return RESULT_OF[body.value];
    },

    /** Thư ký lưu kết quả: server băm lại từng file rồi ghi. items: [{ code, file }] */
    async saveVerification(receiptId, phase, items) {
      const form = new FormData();
      form.append('phase', phase);
      form.append('meta', JSON.stringify(items.map((it) => ({ fileCode: it.code }))));
      items.forEach((it) => form.append('files', it.file, it.file.name));
      await EC.api(`/clerk/receipts/${encodeURIComponent(receiptId)}/verifications`, { method: 'POST', form });
      return upsert(toReceipt(await EC.api(`/clerk/receipts/${encodeURIComponent(receiptId)}`)));
    },
  };
})(window.EC);
