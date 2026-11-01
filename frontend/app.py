import json
import sys
from pathlib import Path

import streamlit as st
from requests.exceptions import RequestException
from web3.exceptions import Web3Exception


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hashutils import format_vn, hash_stream
from history import load_history


st.set_page_config(
    page_title="EvidenceChain | Bằng chứng số",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

    :root {
        --ink: #17233c;
        --muted: #64748b;
        --teal: #0e8c82;
        --line: #e4eaf0;
        --paper: #f5f8fa;
    }
    .stApp {
        background:
            radial-gradient(ellipse at 82% 0%, rgba(32, 164, 151, .10), transparent 34%),
            var(--paper);
        color: var(--ink);
        font-family: 'DM Sans', sans-serif;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stMainBlockContainer"] { max-width: 1120px; padding-top: 2rem; }
    h1, h2, h3, [data-testid="stMetricValue"] { font-family: 'Manrope', sans-serif; }
    .brand {
        display: flex; align-items: center; gap: 10px; margin: 0 0 2.2rem;
        color: #17233c; font: 800 17px 'Manrope', sans-serif; letter-spacing: -.5px;
    }
    .brand-mark {
        display: grid; place-items: center; width: 36px; height: 36px;
        color: white; border-radius: 12px; background: #0e8c82;
        box-shadow: 0 7px 18px rgba(14, 140, 130, .2);
    }
    .hero-kicker {
        color: var(--teal); font-size: 12px; font-weight: 700;
        letter-spacing: 1.7px; text-transform: uppercase;
    }
    .hero-title {
        margin: 8px 0 10px; color: var(--ink);
        font: 800 clamp(30px, 4vw, 46px)/1.14 'Manrope', sans-serif;
        letter-spacing: -1.9px;
    }
    .hero-copy { max-width: 620px; color: var(--muted); font-size: 16px; line-height: 1.7; }
    .trust-row { display: flex; gap: 10px; flex-wrap: wrap; margin: 22px 0 34px; }
    .trust-pill {
        padding: 7px 11px; border: 1px solid var(--line); border-radius: 999px;
        background: rgba(255,255,255,.72); color: #43536b; font-size: 12px; font-weight: 600;
    }
    div[data-testid="stTabs"] button {
        gap: 9px; padding: 13px 20px; color: #64748b; font-weight: 700;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] { color: var(--teal); }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--teal); }
    .panel-heading { margin: 20px 0 4px; color: var(--ink); font: 700 22px 'Manrope', sans-serif; }
    .panel-copy { margin-bottom: 20px; color: var(--muted); line-height: 1.6; }
    div[data-testid="stFileUploader"] section {
        border: 1.5px dashed #cbd7df; border-radius: 16px; background: rgba(255,255,255,.75);
    }
    div[data-testid="stForm"] {
        padding: 20px; border: 1px solid var(--line); border-radius: 18px;
        background: rgba(255,255,255,.78);
    }
    .info-card {
        height: 100%; padding: 20px; border: 1px solid var(--line);
        border-radius: 18px; background: rgba(255,255,255,.72);
    }
    .info-number { color: #0e8c82; font: 800 12px 'Manrope', sans-serif; letter-spacing: 1px; }
    .info-title { margin: 8px 0; color: var(--ink); font: 700 16px 'Manrope', sans-serif; }
    .info-copy { color: var(--muted); font-size: 13px; line-height: 1.6; }
    div.stButton > button, div[data-testid="stFormSubmitButton"] > button {
        min-height: 46px; border: 0; border-radius: 11px; background: var(--teal);
        color: white; font-weight: 700; box-shadow: 0 7px 16px rgba(14, 140, 130, .16);
    }
    div.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
        border: 0; background: #08756e; color: white;
    }
    .footer {
        margin-top: 42px; padding-top: 18px; border-top: 1px solid var(--line);
        color: #8793a3; font-size: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="brand"><span class="brand-mark">E</span> EvidenceChain</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="hero-kicker">Hồ sơ số · Xác thực minh bạch</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Bằng chứng của bạn,<br>được bảo vệ bằng blockchain.</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-copy">Tạo biên nhận cho tệp bằng dấu vân tay SHA-256 và dấu thời gian trên Sepolia. '
    'Bất cứ lúc nào, bạn cũng có thể kiểm tra tệp còn nguyên vẹn hay không.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="trust-row"><span class="trust-pill">◈ SHA-256</span>'
    '<span class="trust-pill">⛓ Ethereum Sepolia</span>'
    '<span class="trust-pill">◷ Dấu thời gian UTC+7</span></div>',
    unsafe_allow_html=True,
)

submit_tab, verify_tab, history_tab = st.tabs(["✦  Tạo biên nhận", "⌕  Kiểm tra tệp", "☰  Lịch sử"])


def tx_link(tx: dict, label: str = "Xem trên Etherscan") -> str:
    """Link Etherscan, hoặc thông báo lỗi nếu giao dịch không gửi được."""
    if "explorerUrl" in tx:
        return f"[{label}]({tx['explorerUrl']})"
    return f"⚠ Lỗi: {tx.get('error', 'không rõ')}"


with submit_tab:
    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.markdown('<div class="panel-heading">Gửi tệp để tạo biên nhận</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="panel-copy">Chọn một hoặc nhiều tệp. Hệ thống tự ghi thời điểm hash xong từng file, '
            'gộp thành bundle hash rồi ghi cả bundle lẫn hash từng file lên blockchain.</div>',
            unsafe_allow_html=True,
        )
        with st.form("create_receipt_form"):
            uploaded_files = st.file_uploader(
                "Tệp cần ghi nhận",
                accept_multiple_files=True,
                help="Tệp được băm tại ứng dụng; nội dung tệp không được tải lên blockchain.",
            )
            submitted = st.form_submit_button("Tạo biên nhận trên Sepolia  →", use_container_width=True)

        if submitted:
            if not uploaded_files:
                st.warning("Vui lòng chọn ít nhất một tệp trước khi tiếp tục.")
            else:
                try:
                    from receipt import create_receipt

                    for uploaded_file in uploaded_files:
                        uploaded_file.seek(0)
                    with st.spinner("Đang hash từng tệp, gửi giao dịch và chờ xác nhận trên Sepolia…"):
                        receipt = create_receipt([(f.name, f) for f in uploaded_files])

                    bundle = receipt["bundle"]
                    receipt_json = json.dumps(receipt, indent=2, ensure_ascii=False)
                    st.success(
                        f"Biên nhận đã được xác nhận trên Sepolia lúc {bundle['tx']['blockTimeVN']} "
                        f"(block #{bundle['tx']['blockNumber']})."
                    )
                    st.markdown(f"**Thời điểm nhận tệp:** {format_vn(receipt['submittedAt'])}")

                    st.markdown("**Bundle hash**")
                    st.code(bundle["bundleHash"], language=None)
                    st.markdown(
                        f"- Habc: `{bundle['habc']}`\n"
                        f"- Habc tính xong lúc: {format_vn(bundle['bundledAt'])}\n"
                        f"- Giao dịch bundle: {tx_link(bundle['tx'])}"
                    )

                    st.markdown("**Hash từng tệp**")
                    rows = ["| Tệp | Hash xong lúc | Hash (Hi) | Giao dịch |", "|---|---|---|---|"]
                    for item in receipt["files"]:
                        rows.append(
                            f"| {item['fileName']} | {format_vn(item['hashedAt'])} | "
                            f"`{item['fileHash'][:16]}…` | {tx_link(item['tx'], 'tx')} |"
                        )
                    st.markdown("\n".join(rows))

                    st.download_button(
                        "Tải biên nhận JSON",
                        data=receipt_json.encode("utf-8"),
                        file_name="evidencechain-receipt.json",
                        mime="application/json",
                        use_container_width=True,
                    )
                except (KeyError, ValueError, RuntimeError, Web3Exception, RequestException) as exc:
                    st.error(f"Không thể tạo biên nhận: {exc}")

    with right:
        st.markdown(
            '<div class="info-card"><div class="info-number">01 — DẤU VÂN TAY</div>'
            '<div class="info-title">Hash + thời điểm cho từng tệp</div>'
            '<div class="info-copy">Mỗi tệp có Hi và Hti (hash thời điểm băm xong), gộp thành '
            'Ha = SHA256(Hi ‖ Hti). Nội dung tệp không lên chuỗi.</div><br>'
            '<div class="info-number">02 — GỘP BUNDLE</div>'
            '<div class="info-title">Habc + thời điểm gộp</div>'
            '<div class="info-copy">Các Ha sắp theo Hi giảm dần, Habc = SHA256(Ha ‖ Hb ‖ …), '
            'Bundle = SHA256(Habc ‖ SHA256(thời điểm gộp)).</div><br>'
            '<div class="info-number">03 — BIÊN NHẬN</div>'
            '<div class="info-title">Lưu lại tệp JSON</div>'
            '<div class="info-copy">Biên nhận chứa hash và thời gian từng tệp, bundle hash, '
            'và link Etherscan cho từng giao dịch.</div></div>',
            unsafe_allow_html=True,
        )

with verify_tab:
    st.markdown('<div class="panel-heading">Kiểm tra tính toàn vẹn của tệp</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-copy">Tải lên tệp gốc cùng biên nhận JSON. Hệ thống sẽ so sánh dấu vân tay, '
        'tính lại bundle hash và kiểm tra giao dịch trên Sepolia.</div>',
        unsafe_allow_html=True,
    )
    with st.form("verify_receipt_form"):
        receipt_file = st.file_uploader(
            "Biên nhận EvidenceChain (.json)",
            type=["json"],
            accept_multiple_files=False,
            key="receipt_json_upload",
        )
        evidence_files = st.file_uploader(
            "Tệp cần kiểm tra",
            accept_multiple_files=True,
            key="evidence_files_upload",
            help="Chọn lại tất cả tệp đã có trong biên nhận (đổi tên tệp không ảnh hưởng).",
        )
        verify_submitted = st.form_submit_button("Kiểm tra tệp và giao dịch  →", use_container_width=True)

    if verify_submitted:
        if receipt_file is None or not evidence_files:
            st.warning("Vui lòng tải lên biên nhận JSON và ít nhất một tệp cần kiểm tra.")
        else:
            try:
                receipt_data = json.loads(receipt_file.getvalue().decode("utf-8"))
                for evidence_file in evidence_files:
                    evidence_file.seek(0)
                actual_hashes = [hash_stream(f) for f in evidence_files]

                from receipt import verify_receipt

                with st.spinner("Đang kiểm tra giao dịch trên Sepolia…"):
                    result = verify_receipt(receipt_data, actual_hashes)

                if result["allOk"]:
                    st.success("Tệp nguyên vẹn — hash từng tệp, công thức bundle và giao dịch trên Sepolia đều khớp.")
                elif not result["filesMatch"]:
                    st.error("Tệp không khớp biên nhận. Nội dung đã thay đổi, thiếu tệp hoặc có tệp không thuộc hồ sơ.")
                elif not result["formulaOk"]:
                    st.error("Tính lại bundle hash từ biên nhận không khớp — biên nhận đã bị chỉnh sửa.")
                elif not result["bundleOnChain"]:
                    st.error("Bundle hash không khớp hoặc không xác thực được trên Sepolia.")
                else:
                    st.error("Ít nhất một hash tệp riêng không khớp giao dịch trên Sepolia.")

                if result["missing"]:
                    st.markdown("**Thiếu hoặc bị sửa:** " + ", ".join(f"`{name}`" for name in result["missing"]))
                if result["extraCount"]:
                    st.markdown(f"**Tệp không thuộc hồ sơ:** {result['extraCount']}")
                st.markdown(
                    f"- Tệp: {'Khớp' if result['filesMatch'] else 'Không khớp'}\n"
                    f"- Công thức bundle: {'Khớp' if result['formulaOk'] else 'Không khớp'}\n"
                    f"- Bundle trên Sepolia: {'Khớp' if result['bundleOnChain'] else 'Không khớp'} · "
                    f"{tx_link(receipt_data['bundle']['tx'])}\n"
                    + "\n".join(
                        f"- `{item['fileName']}` trên Sepolia: {'Khớp' if item['ok'] else 'Không khớp'}"
                        for item in result["fileOnChain"]
                    )
                )
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError) as exc:
                st.error(f"Không thể đọc biên nhận: {exc}")
            except (Web3Exception, RequestException) as exc:
                st.error(f"Không thể xác minh trên Sepolia: {exc}")

with history_tab:
    st.markdown('<div class="panel-heading">Lịch sử biên nhận</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-copy">Xem lại các lần đã tạo biên nhận và tổng số tệp đã ghi nhận.</div>',
        unsafe_allow_html=True,
    )
    if st.button("Kiểm tra lịch sử biên nhận", use_container_width=True):
        history = load_history()
        if not history:
            st.info("Chưa có biên nhận nào được tạo.")
        else:
            total_files = sum(item["fileCount"] for item in history)
            st.info(f"Đã tạo **{len(history)}** biên nhận, tổng cộng **{total_files}** tệp đã được ghi nhận.")
            st.dataframe(
                [
                    {
                        "Thời điểm": format_vn(item["submittedAt"]),
                        "Số tệp": item["fileCount"],
                        "Tệp": ", ".join(item["files"]),
                        "Bundle hash": item["bundleHash"],
                        "Giao dịch": item["explorerUrl"],
                    }
                    for item in reversed(history)
                ],
                column_config={"Giao dịch": st.column_config.LinkColumn(display_text="Etherscan")},
                use_container_width=True,
                hide_index=True,
            )

st.markdown(
    '<div class="footer">EvidenceChain · SHA-256 · Ethereum Sepolia · Tệp của bạn không được lưu trữ bởi ứng dụng</div>',
    unsafe_allow_html=True,
)
