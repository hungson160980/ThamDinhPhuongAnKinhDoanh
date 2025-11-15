####################### main.py — PHẦN 1/5 ############################
# PASDV – PHÂN TÍCH PHƯƠNG ÁN SỬ DỤNG VỐN
# Full Streamlit App – Version chuẩn deploy Streamlit Cloud
# Muội viết theo yêu cầu của Huynh ❤️

import streamlit as st
import pandas as pd
import io, re, requests, datetime, base64, tempfile
import matplotlib.pyplot as plt

# ---- Import DOCX an toàn (python-docx hoặc docx) ----
try:
    from docx import Document
except ImportError:
    import docx
    Document = docx.Document

# ---------------------------
# Format số đẹp (1.000.000)
# ---------------------------
def format_thousands(x, decimals=0):
    if x is None:
        return ""
    try:
        if decimals == 0:
            s = f"{x:,.0f}"
            return s.replace(",", ".")
        else:
            s = ("{:,." + str(decimals) + "f}").format(x)
            return s.replace(",", ".")
    except:
        return str(x)

# ---------------------------
# Parse số từ văn bản
# ---------------------------
def parse_int_from_text(s):
    if not s:
        return None
    nums = re.findall(r"[\d\.,]+", s)
    cleaned = []
    for n in nums:
        n2 = n.replace(".", "").replace(",", "")
        if n2.isdigit():
            cleaned.append(int(n2))
    if cleaned:
        return max(cleaned)
    return None

# ---------------------------
# Đọc toàn bộ văn bản trong file DOCX
# ---------------------------
def extract_text_from_docx(file_stream):
    doc = Document(file_stream)
    texts = []
    for p in doc.paragraphs:
        if p.text and p.text.strip():
            texts.append(p.text.strip())
    return "\n".join(texts)

# ---------------------------
# Trích xuất dữ liệu từ nội dung docx
# ---------------------------
def extract_data_from_docx_text(text):
    data = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined = "\n".join(lines)

    # ---- Họ tên ----
    name_matches = re.findall(r"Họ và tên[:\s]*([A-Za-zÀ-ỹ\s]+)", joined)
    if name_matches:
        data["name1"] = name_matches[0].strip()

    # ---- Số điện thoại ----
    phone = re.findall(r"\b0\d{8,10}\b", joined)
    if phone:
        data["phone"] = phone[0]

    # ---- Email ----
    email = re.findall(r"[\w\.-]+@[\w\.-]+", joined)
    if email:
        data["email"] = email[0]

    # ---- Địa chỉ ----
    addr = re.findall(r"Nơi cư trú[:\s]*([^\n]+)", joined)
    if addr:
        data["address"] = addr[0].strip()

    # ---- Tổng nhu cầu vốn ----
    total = re.search(r"Tổng nhu cầu vốn[:\s]*([\d\.\,\s]+)", joined)
    if total:
        data["total_need"] = parse_int_from_text(total.group(1))

    # ---- Vốn đối ứng ----
    vdd = re.search(r"Vốn đối ứng[:\s]*([\d\.\,\s]+)", joined)
    if vdd:
        data["own_capital"] = parse_int_from_text(vdd.group(1))

    # ---- Số tiền vay ----
    loan = re.search(r"Vốn vay Agribank.*?([\d\.\,\s]+)", joined)
    if loan:
        data["loan_amount"] = parse_int_from_text(loan.group(1))

    # ---- Lãi suất ----
    ir = re.search(r"Lãi suất[:\s]*([\d\.,]+)", joined)
    if ir:
        try:
            data["interest_rate"] = float(ir.group(1).replace(",", "."))
        except:
            pass

    # ---- Thời hạn ----
    term = re.search(r"Thời hạn vay[:\s]*(\d+)\s*tháng", joined)
    if term:
        data["term_months"] = int(term.group(1))

    # ---- Giá trị tài sản ----
    asset = re.search(r"Giá trị[:\s]*([\d\.,]+)", joined)
    if asset:
        data["asset_value"] = parse_int_from_text(asset.group(1))

    # ---- Thu nhập hàng tháng ----
    inc = re.search(r"Tổng thu nhập ổn định.*?([\d\.\,]+)", joined)
    if inc:
        data["monthly_income"] = parse_int_from_text(inc.group(1))

    # ---- Chi phí ----
    exp = re.search(r"Tổng chi phí hàng tháng[:\s]*([\d\.\,]+)", joined)
    if exp:
        data["monthly_expense"] = parse_int_from_text(exp.group(1))

    return data

# ---------------------------
# Tính toán tài chính: PMT
# ---------------------------
def annuity_monthly_payment(loan_amount, annual_rate_percent, term_months):
    if not loan_amount or not term_months or term_months <= 0:
        return 0
    r = (annual_rate_percent or 0) / 100 / 12
    if r == 0:
        return loan_amount / term_months
    denom = 1 - (1 + r) ** (-term_months)
    if denom == 0:
        return loan_amount / term_months
    return loan_amount * r / denom

# ---------------------------
# Tính các chỉ tiêu
# ---------------------------
def compute_indicators(state):
    loan = state.get("loan_amount", 0) or 0
    rate = state.get("interest_rate", 0) or 0
    term = state.get("term_months", 0) or 0
    income = state.get("monthly_income", 0) or 0
    expense = state.get("monthly_expense", 0) or 0
    asset_val = state.get("asset_value", 0) or 0

    monthly = annuity_monthly_payment(loan, rate, term)
    total_pay = monthly * (term or 1)
    dsr = monthly / income if income else None
    ltv = loan / asset_val * 100 if asset_val else None
    net_cf = income - expense - monthly

    return {
        "monthly_payment": monthly,
        "total_payment": total_pay,
        "dsr": dsr,
        "ltv": ltv,
        "net_cashflow": net_cf
    }

######################## main.py — PHẦN 2 / 5 ###########################

# ==========================
# Lịch trả nợ (Amortization)
# ==========================
def generate_amortization_schedule(loan_amount, annual_rate_percent, term_months, start_date=None):
    if loan_amount is None or term_months is None:
        return pd.DataFrame()
    r = (annual_rate_percent or 0) / 100 / 12
    pmt = annuity_monthly_payment(loan_amount, annual_rate_percent, term_months)
    balance = loan_amount
    rows = []

    if start_date is None:
        start_date = datetime.date.today()

    for i in range(1, term_months + 1):
        interest = balance * r
        principal = pmt - interest
        if principal > balance:
            principal = balance
            pmt = principal + interest
        balance -= principal
        rows.append({
            "Month": i,
            "Date": (start_date + pd.DateOffset(months=i)).strftime("%Y-%m-%d"),
            "Payment": pmt,
            "Principal": principal,
            "Interest": interest,
            "Remaining": max(balance, 0)
        })

    return pd.DataFrame(rows)

# ==========================
# Gemini API wrapper
# ==========================
GEMINI_API_URL = "https://api.example.com/gemini"   # Huynh sẽ thay bằng URL thật

def call_gemini(prompt, api_key, max_tokens=512):
    if not api_key:
        return "Chưa nhập API key!"

    payload = {
        "model": "gemini-2.5-flash",
        "prompt": prompt,
        "max_tokens": max_tokens
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            j = r.json()

            # Phân loại các dạng response (tuỳ backend)
            if isinstance(j, dict):
                for k in ["text", "output", "content", "response"]:
                    if k in j:
                        return j[k]
                if "choices" in j:
                    return j["choices"][0].get("text", "")
            return str(j)
        return f"Lỗi Gemini API: {r.status_code} - {r.text}"

    except Exception as e:
        return f"Lỗi gọi Gemini: {e}"

# ==========================
# Xuất Excel
# ==========================
def df_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="amortization")
    return output.getvalue()

# ==========================
# Xuất PDF bằng reportlab
# ==========================
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet

def create_pdf_report(state, indicators, chart_image_bytes=None):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(tmp.name, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("BÁO CÁO THẨM ĐỊNH PHƯƠNG ÁN SỬ DỤNG VỐN", styles["Title"]))
    elems.append(Spacer(1, 12))

    # ---- Thông tin khách hàng ----
    elems.append(Paragraph(f"Khách hàng: {state.get('name1','')}", styles["Normal"]))
    elems.append(Paragraph(f"Địa chỉ: {state.get('address','')}", styles["Normal"]))
    elems.append(Paragraph(f"Số điện thoại: {state.get('phone','')}", styles["Normal"]))
    elems.append(Spacer(1, 12))

    # ---- Chỉ tiêu ----
    elems.append(Paragraph("CÁC CHỈ TIÊU TÀI CHÍNH", styles["Heading2"]))
    for k, v in indicators.items():
        if v is None:
            disp = "N/A"
        elif k == "dsr":
            disp = f"{v:.2%}"
        elif k == "ltv":
            disp = f"{v:.2f}%"
        else:
            disp = format_thousands(v)
        elems.append(Paragraph(f"{k}: {disp}", styles["Normal"]))

    elems.append(Spacer(1, 12))

    # ---- Biểu đồ ----
    if chart_image_bytes:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        f.write(chart_image_bytes)
        f.flush()
        elems.append(RLImage(f.name, width=400, height=250))

    doc.build(elems)

    with open(tmp.name, "rb") as f:
        return f.read()

# =============================================================
# BẮT ĐẦU ỨNG DỤNG STREAMLIT
# =============================================================
st.set_page_config(page_title="PASDV Analyzer", layout="wide")
st.title("💼 PHÂN TÍCH PHƯƠNG ÁN SỬ DỤNG VỐN (PASDV)")
st.caption("Ứng dụng hỗ trợ cán bộ tín dụng – phiên bản của Huynh ❤️")

# --------------------------
# Sidebar: API key Gemini
# --------------------------
st.sidebar.header("Cấu hình hệ thống")
api_key = st.sidebar.text_input("🔑 API Key Gemini", type="password")

export_choice = st.sidebar.selectbox(
    "📤 Xuất dữ liệu",
    ["Không xuất", "Xuất Excel lịch trả nợ", "Xuất PDF thẩm định"]
)

# --------------------------
# State khởi tạo
# --------------------------
if "state" not in st.session_state:
    st.session_state["state"] = {
        "name1": "",
        "phone": "",
        "email": "",
        "address": "",
        "total_need": 0,
        "own_capital": 0,
        "loan_amount": 0,
        "interest_rate": 8.5,
        "term_months": 60,
        "asset_value": 0,
        "monthly_income": 0,
        "monthly_expense": 0
    }

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

state = st.session_state["state"]
############################------------------ PHẦN 3
######################## main.py — PHẦN 3 / 5 ###########################

# =============================================================
# Giao diện chính — chia 2 cột
# =============================================================
left_col, right_col = st.columns([1, 3])

# ===========================
# LEFT: Upload & Reset
# ===========================
with left_col:
    st.header("📂 Upload hồ sơ")

    uploaded_file = st.file_uploader("Tải file .docx phương án vay vốn", type=["docx"])

    if uploaded_file:
        text = extract_text_from_docx(uploaded_file)
        parsed = extract_data_from_docx_text(text)

        # nạp lên state
        for k, v in parsed.items():
            if v is not None:
                state[k] = v

        st.success("Đã trích xuất dữ liệu từ file. Huynh kiểm tra bên phải nhé.")
        st.text_area("📄 Nội dung file (rút gọn):", text[:5000], height=200)

    st.markdown("---")

    if st.button("🔄 Reset dữ liệu"):
        st.session_state["state"] = {
            "name1": "",
            "phone": "",
            "email": "",
            "address": "",
            "total_need": 0,
            "own_capital": 0,
            "loan_amount": 0,
            "interest_rate": 8.5,
            "term_months": 60,
            "asset_value": 0,
            "monthly_income": 0,
            "monthly_expense": 0
        }
        st.experimental_rerun()

# =============================================================
# RIGHT: Tabs
# =============================================================
with right_col:
    tabs = st.tabs([
        "1. Định danh",
        "2. Tài chính",
        "3. Tài sản bảo đảm",
        "4. Tính toán",
        "5. Biểu đồ",
        "6. Phân tích AI",
        "7. Chat Gemini",
        "8. Xuất file"
    ])

    # ----------------------------------------------------------
    # Helper: Numeric with +/-
    # ----------------------------------------------------------
    def numeric_editor(label, key, step=1000000):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            txt = st.text_input(label, value=str(state.get(key, 0)))
            try:
                val = int(txt.replace(".", "").replace(",", ""))
                state[key] = val
            except:
                pass
        with c2:
            if st.button("+", key=f"plus_{key}"):
                state[key] = state.get(key, 0) + step
        with c3:
            if st.button("-", key=f"minus_{key}"):
                state[key] = max(0, state.get(key, 0) - step)

    # =========================================================
    # TAB 1 – ĐỊNH DANH
    # =========================================================
    with tabs[0]:
        st.subheader("📌 Thông tin định danh khách hàng")

        col1, col2 = st.columns(2)
        with col1:
            state["name1"] = st.text_input("Họ và tên", value=state.get("name1", ""))
            state["address"] = st.text_input("Địa chỉ", value=state.get("address", ""))
        with col2:
            state["phone"] = st.text_input("Số điện thoại", value=state.get("phone", ""))
            state["email"] = st.text_input("Email", value=state.get("email", ""))

    # =========================================================
    # TAB 2 – TÀI CHÍNH
    # =========================================================
    with tabs[1]:
        st.subheader("💰 Thông tin tài chính & phương án vay")

        state["purpose"] = st.text_input("Mục đích vay", value=state.get("purpose", "Mua nhà"))

        numeric_editor("Tổng nhu cầu vốn (VND)", "total_need", step=100000000)
        numeric_editor("Vốn đối ứng (VND)", "own_capital", step=100000000)
        numeric_editor("Số tiền vay (VND)", "loan_amount", step=100000000)

        cA, cB = st.columns(2)
        with cA:
            state["interest_rate"] = st.number_input(
                "Lãi suất (%/năm)", value=float(state.get("interest_rate", 8.5)))
        with cB:
            state["term_months"] = st.number_input(
                "Thời hạn vay (tháng)", value=int(state.get("term_months", 60)), min_value=1)

    # =========================================================
    # TAB 3 – TÀI SẢN BẢO ĐẢM
    # =========================================================
    with tabs[2]:
        st.subheader("🏠 Tài sản bảo đảm")

        state["asset_type"] = st.text_input("Loại tài sản", value=state.get("asset_type", "Nhà & đất"))
        numeric_editor("Giá trị tài sản (VND)", "asset_value", step=100000000)

        state["asset_address"] = st.text_input("Địa chỉ tài sản", value=state.get("asset_address", ""))
        state["asset_docs"] = st.text_input("Giấy tờ pháp lý", value=state.get("asset_docs", "GCN QSDĐ"))

    # =========================================================
    # TAB 4 – TÍNH TOÁN
    # =========================================================
    with tabs[3]:
        st.subheader("📊 Kết quả tính toán")

        indicators = compute_indicators(state)

        st.metric("💵 Thanh toán hàng tháng", format_thousands(indicators["monthly_payment"]))
        st.metric("LTV (%)", f"{indicators['ltv']:.2f}%" if indicators["ltv"] else "N/A")
        st.metric("DSR", f"{indicators['dsr']:.2%}" if indicators["dsr"] else "N/A")

        st.write("### Chi tiết chỉ tiêu")
        st.write({
            "monthly_payment": format_thousands(indicators["monthly_payment"]),
            "total_payment": format_thousands(indicators["total_payment"]),
            "net_cashflow": format_thousands(indicators["net_cashflow"]),
            "dsr": f"{indicators['dsr']:.2%}" if indicators["dsr"] else "N/A",
            "ltv": f"{indicators['ltv']:.2f}%" if indicators["ltv"] else "N/A",
        })

        if st.button("📅 Tạo lịch trả nợ"):
            df_am = generate_amortization_schedule(
                state.get("loan_amount", 0),
                state.get("interest_rate", 0),
                state.get("term_months", 0),
            )
            st.session_state["amortization"] = df_am
            st.success("Đã tạo lịch trả nợ! Xem tab ‘Xuất file’.")
######################## main.py — PHẦN 4 / 5 ###########################

    # =========================================================
    # TAB 5 – BIỂU ĐỒ
    # =========================================================
    with tabs[4]:
        st.subheader("📈 Biểu đồ các chỉ tiêu")

        df_am = st.session_state.get("amortization")

        if df_am is None:
            df_am = generate_amortization_schedule(
                state.get("loan_amount", 0),
                state.get("interest_rate", 0),
                state.get("term_months", 0),
            )

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df_am["Month"], df_am["Payment"], label="Payment")
        ax.plot(df_am["Month"], df_am["Principal"], label="Principal")
        ax.plot(df_am["Month"], df_am["Interest"], label="Interest")
        ax.legend()
        ax.set_xlabel("Tháng")
        ax.set_ylabel("VND")
        ax.set_title("Biểu đồ dòng tiền trả nợ")
        st.pyplot(fig)

        # Lưu chart để nhúng PDF
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        chart_bytes = buf.getvalue()

    # =========================================================
    # TAB 6 – PHÂN TÍCH AI
    # =========================================================
    with tabs[5]:
        st.subheader("🤖 Phân tích bằng Gemini AI")

        # -----------------------------
        # 1) Phân tích dựa vào FILE UPLOAD
        # -----------------------------
        st.markdown("### 📝 Phần 1 – Phân tích dựa vào file upload")

        if st.button("Phân tích File Upload"):
            if not uploaded_file:
                st.warning("Chưa có file upload!")
            else:
                uploaded_file.seek(0)
                raw_text = extract_text_from_docx(uploaded_file)

                prompt = (
                    "Hãy phân tích hồ sơ vay vốn dưới đây, tập trung vào rủi ro, "
                    "khả năng trả nợ, nguồn trả nợ, tài sản bảo đảm và kết luận đề xuất.\n\n"
                    f"--- DỮ LIỆU TỪ FILE UPLOAD ---\n{raw_text[:5000]}"
                )

                with st.spinner("Gemini đang phân tích…"):
                    ai_result = call_gemini(prompt, api_key)
                    st.text_area("Kết quả phân tích File Upload", ai_result, height=300)

        # -----------------------------
        # 2) Phân tích dựa vào dữ liệu chỉnh sửa
        # -----------------------------
        st.markdown("### ✏️ Phần 2 – Phân tích dựa vào dữ liệu đã chỉnh sửa")

        if st.button("Phân tích dữ liệu đã nhập"):
            prompt2 = (
                "Hãy phân tích hồ sơ vay vốn dựa trên dữ liệu nhập liệu phía người dùng.\n\n"
                "--- DỮ LIỆU NHẬP LIỆU ---\n"
                f"{state}\n\n"
                "--- CÁC CHỈ TIÊU TÍNH TOÁN ---\n"
                f"{compute_indicators(state)}"
            )

            with st.spinner("Gemini đang phân tích…"):
                ai_result2 = call_gemini(prompt2, api_key)
                st.text_area("Kết quả phân tích Dữ liệu nhập", ai_result2, height=300)

    # =========================================================
    # TAB 7 – CHAT GEMINI
    # =========================================================
    with tabs[6]:
        st.subheader("💬 Chat với Gemini AI")

        chat_input = st.text_input("Nhập câu hỏi:")

        c_send, c_clear = st.columns([1, 1])
        with c_send:
            if st.button("Gửi"):
                if not chat_input:
                    st.warning("Nhập nội dung trước khi gửi!")
                else:
                    st.session_state["chat_history"].append(("User", chat_input))
                    reply = call_gemini(chat_input, api_key)
                    st.session_state["chat_history"].append(("Gemini", reply))
                    st.experimental_rerun()

        with c_clear:
            if st.button("Xóa hội thoại"):
                st.session_state["chat_history"] = []
                st.experimental_rerun()

        # Hiển thị chat
        for role, msg in st.session_state["chat_history"]:
            if role == "User":
                st.markdown(f"**🧑 Khách hàng:** {msg}")
            else:
                st.markdown(f"**🤖 Gemini:** {msg}")

    # =========================================================
    # TAB 8 – XUẤT FILE
    # =========================================================
    with tabs[7]:
        st.subheader("📤 Xuất file")

        df_am = st.session_state.get("amortization")

        if df_am is None:
            df_am = generate_amortization_schedule(
                state.get("loan_amount", 0),
                state.get("interest_rate", 0),
                state.get("term_months", 0),
            )

        # =====================================
        # Xuất Excel
        # =====================================
        if st.button("⬇️ Xuất Excel – Lịch trả nợ"):
            xls_bytes = df_to_excel_bytes(df_am)
            st.download_button(
                "Tải file Excel",
                data=xls_bytes,
                file_name="lich_tra_no.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # =====================================
        # Xuất PDF
        # =====================================
        if st.button("⬇️ Xuất PDF – Báo cáo thẩm định"):
            indicators = compute_indicators(state)

            # tạo biểu đồ mới để nhúng
            fig2, ax2 = plt.subplots(figsize=(8,3))
            ax2.plot(df_am["Month"], df_am["Payment"])
            ax2.set_title("Biểu đồ nghĩa vụ trả nợ")
            buf2 = io.BytesIO()
            fig2.savefig(buf2, format="png", bbox_inches="tight")
            pdf_chart_bytes = buf2.getvalue()

            pdf_data = create_pdf_report(state, indicators, chart_image_bytes=pdf_chart_bytes)

            st.download_button(
                "Tải PDF",
                data=pdf_data,
                file_name="bao_cao_tham_dinh.pdf",
                mime="application/pdf"
            )

######################## main.py — PHẦN 5 / 5 ###########################

# ===========================
# Sidebar thông tin
# ===========================
st.sidebar.markdown("---")
st.sidebar.write("🧡 Ứng dụng PASDV – Hoàn chỉnh theo yêu cầu của Huynh.")
st.sidebar.write("Nếu cần thêm tính năng: ký số PDF, API Agribank, lưu DB, multi-user… Muội làm tiếp cho Huynh.")

# ===========================
# KẾT THÚC ỨNG DỤNG
# ===========================
