# main.py
"""
Streamlit app: Phân tích Phương Án Sử Dụng Vốn (PASDV)
Tính năng:
- Upload .docx và trích xuất thông tin cơ bản
- Chỉnh sửa thủ công +/-
- Tính toán các chỉ tiêu tài chính, DSR, LTV, dòng tiền...
- Biểu đồ (matplotlib)
- Gọi Gemini (mẫu wrapper) để phân tích AI
- Chatbox Gemini với nút xóa
- Xuất Excel (kế hoạch trả nợ) và PDF báo cáo
- Format số: phần nghìn phân cách bằng dấu "."
- Session-based (không dùng DB)
Author: trợ lý (Muội) - viết theo yêu cầu của Sếp
"""

import streamlit as st
import pandas as pd
import io
import re
from docx import Document
import matplotlib.pyplot as plt
import base64
import requests
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet
import tempfile
import math
import datetime

# ---------------------------
# Utility helpers
# ---------------------------

def format_thousands(x, decimals=0):
    """Format number with '.' as thousands separator and comma as decimal separator if decimals>0."""
    if x is None:
        return ""
    try:
        if decimals == 0:
            s = f"{x:,.0f}"
            return s.replace(",", ".")
        else:
            fmt = f"{{:,.{decimals}f}}".format(x)
            # python f-string handled above, but simpler:
            s = ("{:,." + str(decimals) + "f}").format(x)
            return s.replace(",", ".")
    except Exception:
        return str(x)

def parse_int_from_text(s):
    """Try to extract integer numbers (VND) from a text string."""
    if not s:
        return None
    # remove dots/commas inside numbers, extract largest number
    numbers = re.findall(r'[\d\.,]+', s)
    cleaned = []
    for n in numbers:
        # remove non-digit characters except . and ,
        temp = n.replace(",", "").replace(".", "")
        if temp.isdigit():
            cleaned.append(int(temp))
    if cleaned:
        return max(cleaned)
    return None

def safe_get(d, key, default=""):
    return d.get(key, default)

# ---------------------------
# Docx parsing
# ---------------------------

def extract_text_from_docx(file_stream):
    doc = Document(file_stream)
    texts = []
    for p in doc.paragraphs:
        if p.text and p.text.strip():
            texts.append(p.text.strip())
    return "\n".join(texts)

def extract_data_from_docx_text(text):
    """
    Heuristic extraction based on the sample PASDV.docx structure.
    Return a dict with fields.
    """
    data = {}
    # Normalize newlines
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined = "\n".join(lines)
    # Try to get names: look for lines like 'Họ và tên: Nguyễn Văn Minh -Sinh năm:'
    name_matches = re.findall(r'Họ và tên[:\s]*([A-Za-zÀ-ỹ\s]+)', joined)
    if name_matches:
        # put first two found as primary and secondary if exist
        data['name1'] = name_matches[0].strip()
        if len(name_matches) > 1:
            data['name2'] = name_matches[1].strip()
    # phone and email
    phone = re.findall(r'\b0\d{8,10}\b', joined)
    if phone:
        data['phone'] = phone[0]
    email = re.findall(r'[\w\.-]+@[\w\.-]+', joined)
    if email:
        data['email'] = email[0]
    # addresses
    addr_match = re.findall(r'Nơi cư trú[:\s]*([^\n]+)', joined)
    if addr_match:
        data['address'] = addr_match[0].strip()
    # total demand
    total = re.search(r'Tổng nhu cầu vốn[:\s]*([\d\.,\s]+)đồng', joined, re.IGNORECASE)
    if not total:
        total = re.search(r'Tổng nhu cầu vốn[:\s]*[:\s]*([\d\.,\s]+)', joined, re.IGNORECASE)
    if total:
        n = parse_int_from_text(total.group(1))
        if n: data['total_need'] = n
    else:
        # fallback search for "5.000.000.000" style
        n = parse_int_from_text(joined)
        if n:
            data.setdefault('total_need', n)
    # vốn đối ứng
    vdd = re.search(r'Vốn đối ứng[:\s]*([\d\.,\s]+)', joined, re.IGNORECASE)
    if vdd:
        val = parse_int_from_text(vdd.group(1))
        if val: data['own_capital'] = val
    # loan amount
    loan = re.search(r'Vốn vay Agribank số tiền[:\s]*([\d\.,\s]+)đồng', joined, re.IGNORECASE)
    if loan:
        val = parse_int_from_text(loan.group(1))
        if val: data['loan_amount'] = val
    # interest rate
    ir = re.search(r'Lãi suất[:\s]*([\d\.,\s]+)%', joined, re.IGNORECASE)
    if ir:
        try:
            data['interest_rate'] = float(ir.group(1).replace(",", ".").replace(" ", ""))
        except:
            data['interest_rate'] = None
    else:
        # 'Lãi suất: 8,5%/năm'
        ir2 = re.search(r'(\d+[\.,]?\d*)\s*%/năm', joined)
        if ir2:
            data['interest_rate'] = float(ir2.group(1).replace(",", "."))
    # term
    term = re.search(r'Thời hạn vay[:\s]*([\d]+)\s*tháng', joined, re.IGNORECASE)
    if term:
        data['term_months'] = int(term.group(1))
    else:
        term2 = re.search(r'Thời hạn vay[:\s]*([\d]+)\s*năm', joined, re.IGNORECASE)
        if term2:
            data['term_months'] = int(term2.group(1)) * 12
    # asset value
    asset = re.search(r'Giá trị[:\s]*([\d\.,\s]+)đồng', joined, re.IGNORECASE)
    if asset:
        val = parse_int_from_text(asset.group(1))
        if val: data['asset_value'] = val
    # incomes
    inc = re.findall(r'Tổng thu nhập ổn định hàng tháng[:\s]*([\d\.,\s]+)đ', joined, re.IGNORECASE)
    if inc:
        data['monthly_income'] = parse_int_from_text(inc[0])
    else:
        # look for "Tổng thu nhập ổn định hàng tháng: 100.000.000 đồng"
        m = re.search(r'Tổng thu nhập.*?([\d\.,\s]+)\s*đ', joined, re.IGNORECASE)
        if m:
            data['monthly_income'] = parse_int_from_text(m.group(1))
    # monthly expenses
    exp = re.search(r'Tổng chi phí hàng tháng[:\s]*([\d\.,\s]+)đ', joined, re.IGNORECASE)
    if exp:
        data['monthly_expense'] = parse_int_from_text(exp.group(1))
    # return whatever we found
    return data

# ---------------------------
# Financial calculations
# ---------------------------

def annuity_monthly_payment(loan_amount, annual_rate_percent, term_months):
    """Calculate monthly payment (principal + interest) assuming annuity (fixed payment)."""
    if not loan_amount or not term_months or term_months <= 0:
        return 0
    r = (annual_rate_percent or 0) / 100 / 12
    if r == 0:
        return loan_amount / term_months
    denom = 1 - (1 + r) ** (-term_months)
    if denom == 0:
        return loan_amount / term_months
    payment = loan_amount * r / denom
    return payment

def compute_indicators(state):
    """
    Given session values, compute:
    - monthly_payment
    - total_payment
    - DSR (Debt Service Ratio) = (monthly debt payment) / (monthly income)
    - LTV
    - net monthly cashflow = income - expenses - payment
    """
    loan = state.get('loan_amount', 0) or 0
    rate = state.get('interest_rate', 0) or 0
    term = state.get('term_months', 0) or 0
    income = state.get('monthly_income', 0) or 0
    expense = state.get('monthly_expense', 0) or 0
    asset_value = state.get('asset_value', 0) or 0

    monthly_payment = annuity_monthly_payment(loan, rate, term)
    total_payment = monthly_payment * (term or 1)
    dsr = monthly_payment / income if income and income > 0 else None
    ltv = (loan / asset_value * 100) if asset_value and asset_value > 0 else None
    net_cashflow = income - expense - monthly_payment
    indicators = {
        'monthly_payment': monthly_payment,
        'total_payment': total_payment,
        'dsr': dsr,
        'ltv': ltv,
        'net_cashflow': net_cashflow
    }
    return indicators

def generate_amortization_schedule(loan_amount, annual_rate_percent, term_months, start_date=None):
    """Return DataFrame with amortization schedule (annuity)."""
    if loan_amount is None or term_months is None:
        return pd.DataFrame()
    r = (annual_rate_percent or 0) / 100 / 12
    payment = annuity_monthly_payment(loan_amount, annual_rate_percent, term_months)
    balance = loan_amount
    rows = []
    if start_date is None:
        start_date = datetime.date.today()
    for i in range(1, term_months + 1):
        interest = balance * r
        principal = payment - interest
        if principal > balance:
            principal = balance
            payment = interest + principal
        balance = balance - principal
        rows.append({
            'Month': i,
            'Date': (start_date + pd.DateOffset(months=i)).strftime("%Y-%m-%d"),
            'Payment': payment,
            'Principal': principal,
            'Interest': interest,
            'Remaining': max(balance, 0)
        })
    df = pd.DataFrame(rows)
    return df

# ---------------------------
# Gemini AI wrapper (placeholder)
# ---------------------------

GEMINI_API_URL = "https://api.example.com/gemini"  # <- Sếp thay bằng endpoint thật (Vertex AI / endpoint của service)

def call_gemini(prompt, api_key, max_tokens=512):
    """
    Placeholder wrapper to call Gemini (gemini-2.5-flash).
    Sếp cần thay GEMINI_API_URL cho chính xác, hoặc cấu hình header theo provider.
    """
    if not api_key:
        return "API key chưa được nhập. Vui lòng nhập API key ở sidebar."
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
        resp = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            j = resp.json()
            # Attempt to extract text: adjust depending on provider
            if isinstance(j, dict):
                # Common patterns
                for key in ["text", "output", "content", "response"]:
                    if key in j:
                        return j[key]
                # If choices
                if 'choices' in j and isinstance(j['choices'], list):
                    return j['choices'][0].get('text') or j['choices'][0].get('message', {}).get('content', '')
            return str(j)
        else:
            return f"Error from Gemini API: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"Exception calling Gemini API: {e}"

# ---------------------------
# Export functions
# ---------------------------

def df_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="amortization")
    return output.getvalue()

def create_pdf_report(state, indicators, chart_image_bytes=None):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(tmp.name, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []
    elems.append(Paragraph("BÁO CÁO THẨM ĐỊNH PHƯƠNG ÁN SỬ DỤNG VỐN", styles['Title']))
    elems.append(Spacer(1,12))
    elems.append(Paragraph(f"Khách hàng: {safe_get(state,'name1','')}", styles['Normal']))
    elems.append(Paragraph(f"Số điện thoại: {safe_get(state,'phone','')}", styles['Normal']))
    elems.append(Paragraph(f"Địa chỉ: {safe_get(state,'address','')}", styles['Normal']))
    elems.append(Spacer(1,12))
    elems.append(Paragraph("Các chỉ tiêu tài chính", styles['Heading2']))
    for k,v in indicators.items():
        if v is None:
            display = "N/A"
        elif isinstance(v, (int, float)):
            # format
            if k in ['dsr',]:
                display = f"{v:.2%}"
            else:
                display = format_thousands(v, decimals=0) if abs(v) >= 1 else str(v)
        else:
            display = str(v)
        elems.append(Paragraph(f"{k}: {display}", styles['Normal']))
    elems.append(Spacer(1,12))
    if chart_image_bytes:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        f.write(chart_image_bytes)
        f.flush()
        elems.append(RLImage(f.name, width=400, height=250))
    doc.build(elems)
    with open(tmp.name, "rb") as f:
        data = f.read()
    return data

# ---------------------------
# Streamlit App
# ---------------------------

st.set_page_config(page_title="PASDV Analyzer", layout="wide")
st.title("PASDV — Phân tích Phương Án Sử Dụng Vốn")
st.caption("Ứng dụng demo — Sếp có thể chỉnh endpoint Gemini trong code nếu cần")

# Sidebar: API Key and options
st.sidebar.header("Cấu hình")
api_key = st.sidebar.text_input("Nhập API key Gemini (gemini-2.5-flash)", type="password")
st.sidebar.write("Chọn chức năng xuất:")
export_choice = st.sidebar.selectbox("Loại xuất", [
    "Không xuất",
    "Xuất bảng kê kế hoạch trả nợ (Excel)",
    "Xuất báo cáo thẩm định (PDF)"
])

# Initialize session state
if 'state' not in st.session_state:
    st.session_state['state'] = {
        'name1': '',
        'phone': '',
        'address': '',
        'email': '',
        'total_need': 0,
        'own_capital': 0,
        'loan_amount': 0,
        'interest_rate': 8.5,
        'term_months': 60,
        'asset_value': 0,
        'monthly_income': 0,
        'monthly_expense': 0
    }
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []

state = st.session_state['state']

# Layout: left column for upload + controls, right for tabs
left_col, right_col = st.columns([1,3])

with left_col:
    st.header("Upload / Controls")
    uploaded_file = st.file_uploader("Upload file .docx phương án vay vốn", type=["docx"])
    if uploaded_file:
        text = extract_text_from_docx(uploaded_file)
        parsed = extract_data_from_docx_text(text)
        # merge parsed into session state (but allow manual override)
        for k,v in parsed.items():
            # only set if present and currently empty/zero
            if v is not None:
                state[k] = v
        st.success("Đã trích xuất từ file. Vui lòng kiểm tra các tab và chỉnh sửa nếu cần.")
        st.write("Tóm tắt trích xuất:")
        st.text_area("Raw extracted text (preview)", text[:5000], height=200)
    st.markdown("---")
    if st.button("Reset dữ liệu"):
        st.session_state['state'] = {
            'name1': '',
            'phone': '',
            'address': '',
            'email': '',
            'total_need': 0,
            'own_capital': 0,
            'loan_amount': 0,
            'interest_rate': 8.5,
            'term_months': 60,
            'asset_value': 0,
            'monthly_income': 0,
            'monthly_expense': 0
        }
        st.experimental_rerun()

# Right area: Tabs
with right_col:
    tabs = st.tabs(["1. Định danh", "2. Tài chính", "3. TSĐB", "4. Tính toán", "5. Biểu đồ", "6. Phân tích AI", "7. Chat Gemini", "8. Xuất file"])

    # Tab 1: Định danh
    with tabs[0]:
        st.subheader("Thông tin định danh khách hàng")
        col1, col2 = st.columns([2,1])
        with col1:
            state['name1'] = st.text_input("Họ và tên khách hàng", value=state.get('name1',''))
            state['address'] = st.text_input("Địa chỉ", value=state.get('address',''))
        with col2:
            state['phone'] = st.text_input("Số điện thoại", value=state.get('phone',''))
            state['email'] = st.text_input("Email", value=state.get('email',''))

    # Helper to render numeric with +/- buttons
    def numeric_editor(label, key, step=1000000):
        col_a, col_b, col_c = st.columns([3,1,1])
        with col_a:
            # display formatted
            val = state.get(key, 0) or 0
            txt = st.text_input(label, value=str(val))
            try:
                parsed = int(float(txt.replace(".","").replace(",","")))
                state[key] = parsed
            except:
                # keep previous
                pass
        with col_b:
            if st.button("+", key=f"plus_{key}"):
                state[key] = (state.get(key,0) or 0) + step
        with col_c:
            if st.button("-", key=f"minus_{key}"):
                state[key] = max(0, (state.get(key,0) or 0) - step)

    # Tab 2: Tài chính
    with tabs[1]:
        st.subheader("Thông tin tài chính / phương án")
        state['purpose'] = st.text_input("Mục đích vay", value=state.get('purpose','Mua nhà'))
        numeric_editor("Tổng nhu cầu vốn (VND)", 'total_need', step=100000000)
        numeric_editor("Vốn đối ứng (VND)", 'own_capital', step=100000000)
        numeric_editor("Số tiền vay (VND)", 'loan_amount', step=100000000)
        col_a, col_b = st.columns(2)
        with col_a:
            ir = st.number_input("Lãi suất (%/năm)", value=float(state.get('interest_rate',8.5)))
            state['interest_rate'] = float(ir)
        with col_b:
            term_years = st.number_input("Thời hạn (tháng)", min_value=1, value=int(state.get('term_months',60)))
            state['term_months'] = int(term_years)

    # Tab 3: Tài sản đảm bảo
    with tabs[2]:
        st.subheader("Tài sản đảm bảo")
        state['asset_type'] = st.text_input("Loại tài sản", value=state.get('asset_type','Nhà & đất'))
        numeric_editor("Giá trị tài sản (VND)", 'asset_value', step=100000000)
        state['asset_address'] = st.text_input("Địa chỉ tài sản", value=state.get('asset_address',''))
        state['asset_docs'] = st.text_input("Giấy tờ pháp lý", value=state.get('asset_docs','GCN QSDĐ'))

    # Tab 4: Tính toán
    with tabs[3]:
        st.subheader("Kết quả tính toán")
        indicators = compute_indicators(state)
        st.metric("Thanh toán hàng tháng (ước tính)", format_thousands(indicators['monthly_payment'],0))
        st.metric("LTV (%)", f"{indicators['ltv']:.2f}%" if indicators['ltv'] else "N/A")
        st.metric("DSR", f"{indicators['dsr']:.2%}" if indicators['dsr'] else "N/A")
        st.write("Chi tiết:")
        st.write({
            "monthly_payment": format_thousands(indicators['monthly_payment'],0),
            "total_payment": format_thousands(indicators['total_payment'],0),
            "net_cashflow": format_thousands(indicators['net_cashflow'],0),
            "dsr": f"{indicators['dsr']:.2%}" if indicators['dsr'] else "N/A",
            "ltv": f"{indicators['ltv']:.2f}%" if indicators['ltv'] else "N/A"
        })
        if st.button("Tạo lịch trả nợ (amortization)"):
            df_am = generate_amortization_schedule(state.get('loan_amount',0), state.get('interest_rate',0), state.get('term_months',0))
            st.session_state['amortization'] = df_am
            st.success("Đã tạo lịch trả nợ. Chuyển sang tab 'Xuất file' để tải về.")

    # Tab 5: Biểu đồ
    with tabs[4]:
        st.subheader("Biểu đồ chỉ tiêu")
        df = st.session_state.get('amortization', None)
        if df is None:
            df = generate_amortization_schedule(state.get('loan_amount',0), state.get('interest_rate',0), state.get('term_months',0))
        # plot monthly payment vs principal vs interest
        fig, ax = plt.subplots(figsize=(9,4))
        ax.plot(df['Month'], df['Payment'], label='Payment')
        ax.plot(df['Month'], df['Principal'], label='Principal')
        ax.plot(df['Month'], df['Interest'], label='Interest')
        ax.set_xlabel('Month')
        ax.set_ylabel('VND')
        ax.legend()
        st.pyplot(fig)
        # capture chart bytes for PDF
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        chart_bytes = buf.getvalue()

    # Tab 6: Phân tích AI Gemini
    with tabs[5]:
        st.subheader("Phân tích AI (Gemini)")
        st.markdown("**Phân tích A** — Dựa trên file Upload (nguồn: file upload)")
        if st.button("Phân tích File Upload"):
            # prepare prompt from uploaded text (if exists)
            if not uploaded_file:
                st.warning("Chưa upload file. Vui lòng upload file .docx trước.")
            else:
                # read raw text again
                uploaded_file.seek(0)
                raw_text = extract_text_from_docx(uploaded_file)
                prompt = f"Hãy phân tích phương án vay vốn sau đây, tập trung vào rủi ro, khả năng trả nợ, khuyến nghị. Dữ liệu gốc:\n\n{raw_text[:4000]}"
                with st.spinner("Gọi Gemini..."):
                    out = call_gemini(prompt, api_key)
                    st.text_area("Phân tích (dựa trên file upload)", value=out, height=300)

        st.markdown("**Phân tích B** — Dựa trên dữ liệu nhập/chỉnh sửa (nguồn: dữ liệu sau khi hiệu chỉnh)")
        if st.button("Phân tích Dữ liệu đã chỉnh sửa"):
            prompt2 = f"Hãy phân tích dựa trên các chỉ số sau: \n{state}\nCác chỉ số tính toán: {compute_indicators(state)}\nĐưa ra kết luận/rủi ro/đề xuất chi tiết chuyên sâu."
            with st.spinner("Gọi Gemini..."):
                out2 = call_gemini(prompt2, api_key)
                st.text_area("Phân tích (dựa trên dữ liệu đã chỉnh)", value=out2, height=300)

    # Tab 7: Chatbox Gemini
    with tabs[6]:
        st.subheader("Chat với Gemini")
        chat_input = st.text_input("Nhập câu hỏi cho Gemini:", key="chat_input")
        col_send, col_clear = st.columns([1,1])
        with col_send:
            if st.button("Gửi", key="chat_send"):
                if not chat_input:
                    st.warning("Nhập câu hỏi trước khi gửi.")
                else:
                    st.session_state['chat_history'].append(("User", chat_input))
                    with st.spinner("Gọi Gemini..."):
                        resp = call_gemini(chat_input, api_key, max_tokens=300)
                        st.session_state['chat_history'].append(("Gemini", resp))
                        st.experimental_rerun()
        with col_clear:
            if st.button("Xóa chat", key="chat_clear"):
                st.session_state['chat_history'] = []
                st.success("Đã xóa chat.")
        # display chat history
        for role, content in st.session_state['chat_history']:
            if role == "User":
                st.markdown(f"**Bạn:** {content}")
            else:
                st.markdown(f"**Gemini:** {content}")

    # Tab 8: Xuất file
    with tabs[7]:
        st.subheader("Xuất file & Tải về")
        df_am = st.session_state.get('amortization', None)
        if df_am is None:
            df_am = generate_amortization_schedule(state.get('loan_amount',0), state.get('interest_rate',0), state.get('term_months',0))
        st.write("Chọn một trong các hành động:")
        if st.button("Tải bảng kê kế hoạch trả nợ (Excel)"):
            b = df_to_excel_bytes(df_am)
            st.download_button("Tải Excel", data=b, file_name="ke_ke_tra_no.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if st.button("Tạo & Tải báo cáo thẩm định (PDF)"):
            indicators = compute_indicators(state)
            # create chart bytes
            fig2, ax2 = plt.subplots(figsize=(6,3))
            ax2.plot(df_am['Month'], df_am['Payment'])
            ax2.set_title("Payment over time")
            buf2 = io.BytesIO()
            fig2.savefig(buf2, format='png', bbox_inches='tight')
            chart_bytes = buf2.getvalue()
            pdf_bytes = create_pdf_report(state, indicators, chart_image_bytes=chart_bytes)
            st.download_button("Tải báo cáo PDF", data=pdf_bytes, file_name="bao_cao_tham_dinh.pdf", mime="application/pdf")

# End app
st.sidebar.markdown("---")
st.sidebar.write("Sếp: nếu cần Muội tích hợp lưu vào NAS / DB / ký số / deploy CI/CD thì nói Muội nhé.")
