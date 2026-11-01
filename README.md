# EvidenceChain

Lưu chứng bằng chứng số (ảnh, ghi âm, video, văn bản…) bằng **SHA-256** và ghi dấu lên testnet **Ethereum Sepolia**.
File gốc **không bao giờ lên blockchain** — chỉ có dấu vân tay (hash). Ai giữ file gốc và biên nhận đều có thể tự kiểm tra
file còn nguyên vẹn và đã tồn tại trước thời điểm block được ghi.

> Đây là dự án học tập. Chỉ dùng **ví test** trên Sepolia, không dùng ví có tiền thật.

---

## 1. Cơ chế xử lý

### 1.1. Sơ đồ gộp hash

```
File 1 ─► H1 ─┐                         (t1 = lúc hash xong File 1)
     t1 ─► Ht1 ┴─► Ha = SHA256(H1 ‖ Ht1)
              ⏸ nghỉ ngẫu nhiên 1.00–3.00 giây
File 2 ─► H2 ─┐
     t2 ─► Ht2 ┴─► Hb = SHA256(H2 ‖ Ht2)
              ⏸ nghỉ ngẫu nhiên 1.00–3.00 giây
File 3 ─► H3 ─┐
     t3 ─► Ht3 ┴─► Hc = SHA256(H3 ‖ Ht3)

Ha, Hb, Hc (sắp theo Hi giảm dần) ─► Habc = SHA256(Ha ‖ Hb ‖ Hc)
                    tB = lúc Habc tính xong ─► HtB = SHA256(tB)
                                    Bundle = SHA256(Habc ‖ HtB)
```

### 1.2. Từng bước

| Bước | Công thức | Ghi chú |
|---|---|---|
| Hash file | `Hi = SHA256(nội dung file i)` | Đọc từng khúc 1MB → file lớn (video) không tốn RAM |
| Thời điểm hash | `ti` = giờ VN lúc hash xong, chính xác 1/100 giây | Dạng `2026-11-01T23:53:25.61+07:00`, do **hệ thống tự lấy**, người dùng không nhập |
| Hash thời điểm | `Hti = SHA256(ti)` | Chuỗi UTF-8 |
| Lá của file | `Ha = SHA256(Hi ‖ Hti)` | Gắn nội dung với thời điểm của chính file đó |
| Nghỉ | `sleep(random 1.00–3.00 s)` | Giữa 2 file liên tiếp, để mỗi file có mốc thời gian tách biệt |
| Gộp | `Habc = SHA256(Ha ‖ Hb ‖ …)` | Các lá **sắp theo Hi giảm dần (Z→A)** → thứ tự chọn file không ảnh hưởng kết quả |
| Bundle | `Bundle = SHA256(Habc ‖ SHA256(tB))` | `tB` = lúc Habc tính xong |

Ký hiệu `‖` là **nối 32 byte nhị phân** của từng hash (không phải nối chuỗi hex). Vì mỗi hash dài cố định 32 byte,
cách ghép không thể bị hiểu nhầm ranh giới. Toàn bộ nằm trong [`hashutils.py`](hashutils.py).

> Vì sao không dùng XOR / cộng / nhân để gộp? Các phép này không phải hàm băm: XOR làm 2 file trùng nhau tự triệt tiêu
> (H ⊕ H = 0) và có thể bị tấn công tìm bộ file khác cho cùng kết quả. Bước gộp cuối luôn là SHA-256.

### 1.3. Ghi lên Sepolia

Không dùng smart contract. Mỗi hash được ghi bằng **1 giao dịch 0 ETH gửi cho chính ví mình**, hash nằm trong trường
`data` (`0x` + hash). Mỗi lần nộp tạo **N + 1 giao dịch**:

- 1 giao dịch chứa **Bundle**
- N giao dịch, mỗi giao dịch chứa **Hi** (hash nội dung) của một file

Nếu một giao dịch file bị lỗi sau khi bundle đã lên chain, biên nhận vẫn được tạo và ghi lỗi tại file đó (không mất
dấu bundle đã trả phí). Xem [`chain.py`](chain.py).

### 1.4. Về thời gian

- `hashedAt`, `bundledAt` là **giờ của máy chủ** — hữu ích để mô tả quy trình, nhưng do hệ thống tự ghi.
- **Giờ của block** (`blockTimeVN`) mới là mốc do blockchain xác nhận: bằng chứng chắc chắn **đã tồn tại trước** thời điểm đó.

---

## 2. Biên nhận (receipt JSON)

```jsonc
{
  "bundleScheme": "per-file-time-v2",
  "algorithm": "SHA-256",
  "network": "Sepolia",
  "anchoredBy": "0x…",                 // ví đã ghi
  "submittedAt": "2026-11-01T23:53:25.61+07:00",
  "files": [
    {
      "fileName": "anhchup.jpg",
      "fileHash": "4c9b…",              // Hi
      "hashedAt": "2026-11-01T23:53:25.61+07:00",   // ti
      "timeHash": "…",                  // Hti
      "leafHash": "…",                  // Ha
      "sleepAfterSeconds": 2.25,
      "tx": { "txHash": "0x…", "explorerUrl": "https://sepolia.etherscan.io/tx/0x…",
              "blockNumber": 12042325, "blockTimeVN": "01/11/2026 23:53:48", "…": "…" }
    }
  ],
  "bundle": {
    "order": ["…"],                     // thứ tự Hi đã dùng khi gộp
    "habc": "…",
    "bundledAt": "2026-11-01T23:53:30.56+07:00",
    "bundleTimeHash": "…",
    "bundleHash": "a6b1…",
    "tx": { "txHash": "0x…", "explorerUrl": "…", "blockNumber": 12042324, "blockTimeVN": "…" }
  }
}
```

Mỗi lần tạo biên nhận thành công, một dòng tóm tắt được ghi vào `history.json` (tab **Lịch sử**).

## 3. Cách kiểm tra (tab "Kiểm tra tệp" hoặc tự làm tay)

1. Hash lại từng file gốc, so với `fileHash` trong biên nhận (so theo **hash**, đổi tên file không ảnh hưởng).
2. Từ `fileHash` + `hashedAt` + `bundledAt` trong biên nhận, tính lại `Ha…`, `habc`, `bundleHash` theo mục 1.2 — phải khớp.
   Nếu ai sửa thời gian hay hash trong biên nhận, bước này sẽ sai.
3. Mở `explorerUrl` trên Etherscan: giao dịch thành công, gửi từ `anchoredBy`, và **Input Data** = `0x` + hash tương ứng.

---

## 4. Cấu trúc dự án

```
EvidenceChain/
├── hashutils.py      # Hash file/timestamp, gộp bundle theo sơ đồ
├── chain.py          # Ghi hash lên Sepolia, kiểm tra giao dịch
├── receipt.py        # Quy trình tạo + kiểm tra biên nhận
├── history.py        # Lịch sử biên nhận (history.json)
├── main.py           # Chạy thử bằng dòng lệnh
├── frontend/app.py   # Giao diện Streamlit: Tạo biên nhận / Kiểm tra tệp / Lịch sử
├── requirements.txt
└── render.yaml       # Cấu hình deploy lên Render
```

## 5. Chạy trên máy

```bash
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Tạo file `.env` (đã nằm trong `.gitignore`, **không commit**):

```
SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
PRIVATE_KEY=0x...khóa_ví_test
```

Xin Sepolia ETH miễn phí từ một faucet cho ví test, rồi chạy:

```bash
streamlit run frontend/app.py    # giao diện web
python main.py                   # hoặc chạy thử dòng lệnh, ra receipt.json
```

## 6. Deploy lên Render

1. Trên [Render](https://render.com): **New → Blueprint**, chọn repo này. Render đọc `render.yaml`.
2. Khi được hỏi, nhập `PRIVATE_KEY` (khóa ví test). `SEPOLIA_RPC_URL` đã có sẵn giá trị mặc định.
3. Đợi build xong, mở URL dịch vụ.

Lưu ý khi deploy:

- Gói free của Render có ổ đĩa **tạm thời**: `history.json` sẽ mất khi dịch vụ khởi động lại hoặc deploy lại.
- Ai có URL đều có thể bấm "Tạo biên nhận" và tiêu Sepolia ETH của ví test — chỉ để ví test, ít tiền.
- Gói free sẽ "ngủ" khi không có truy cập, lần mở đầu tiên có thể mất ~1 phút.

## 7. Deploy lên Streamlit Community Cloud

1. Vào [share.streamlit.io](https://share.streamlit.io), đăng nhập bằng GitHub.
2. **Create app → Deploy a public app from GitHub**:
   - Repository: `thienAG4/evidence-anchor`, Branch: `main`, Main file path: `frontend/app.py`
   - **Advanced settings → Python 3.12**, và ô **Secrets**:

     ```toml
     SEPOLIA_RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
     PRIVATE_KEY = "0x...khóa_ví_test"
     ```
3. Bấm **Deploy**. Streamlit Cloud cài `requirements.txt` ở thư mục gốc; các secret cấp cao nhất được đưa vào
   biến môi trường nên `chain.py` đọc `os.environ` như khi chạy trên máy.

Các lưu ý về ổ đĩa tạm (`history.json`) và việc người khác tiêu ETH của ví test ở mục 6 cũng áp dụng ở đây.

## 8. Bảo mật

- Không bao giờ commit `.env` hay private key. Nếu lỡ commit, coi như khóa đã lộ và đổi ví.
- Hash từng file được ghi **công khai**: ai đã có sẵn một bản file có thể kiểm tra nó có trong hồ sơ hay không.
- Giữ file gốc cẩn thận — mất file gốc thì hash trên chain không còn để đối chiếu.
