####################### main.py — PHIÊN BẢN UI HIỆN ĐẠI ############################
# PASDV – PHÂN TÍCH PHƯƠNG ÁN SỬ DỤNG VỐN
# Modern UI Version with Enhanced Design
# Muội viết theo yêu cầu của Huynh ❤️

import streamlit as st
import pandas as pd
import io, re, requests, datetime, base64, tempfile
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px

# ---- Import DOCX an toàn ----
try:
    from docx import Document
except ImportError:
    import docx
    Document = docx.Document

# ==========================
# CUSTOM CSS - UI HIỆN ĐẠI
# ==========================
def load_custom_css():
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main Container */
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 0;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3c72 0%, #2a5298 100%);
        color: white;
    }
    
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stSelectbox select {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: white;
        border-radius: 10px;
        padding: 10px;
    }
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] label {
        color: white !important;
    }
    
    /* Card Style */
    .card {
        background: white;
        border-radius: 20px;
        padding: 30px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.15);
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        margin: 10px 0;
    }
    
    .metric-value {
        font-size: 2.5em;
        font-weight: 700;
        margin: 10px 0;
    }
    
    .metric-label {
        font-size: 0.9em;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px 30px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
    }
    
    /* Input Fields */
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div>select {
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        padding: 12px;
        transition: border-color 0.3s ease;
    }
    
    .stTextInput>div>div>input:focus,
    .stNumberInput>div>div>input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: white;
        border-radius: 15px;
        padding: 10px;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.05);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 12px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* File Uploader */
    [data-testid="stFileUploader"] {
        background: white;
        border: 2px dashed #667eea;
        border-radius: 15px;
        padding: 30px;
        text-align: center;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #2d3748;
        font-weight: 700;
    }
    
    /* Success/Warning/Error Messages */
    .stSuccess, .stWarning, .stError, .stInfo {
        border-radius: 10px;
        padding: 15px;
    }
    
    /* DataFrame Styling */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Title Animation */
    @keyframes fadeInDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .main-title {
        animation: fadeInDown 0.8s ease;
    }
    
    /* Progress Bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #5568d3;
    }
    </style>
    """, unsafe_allow_html=True)

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

    # ---- Địa chỉ tài sản ----
    asset_addr = re.search(r"(?:Địa chỉ tài sản|Tài sản tại)[:\s]*([^\n]+)", joined)
    if asset_addr:
        data["asset_address"] = asset_addr.group(1).strip()

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
GEMINI_API_URL = "https://api.example.com/gemini"

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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def create_pdf_report(state, indicators, chart_image_bytes=None):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(tmp.name, pagesize=A4)

    # Register Vietnamese font - sử dụng DejaVu Sans có sẵn trong hầu hết hệ thống
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
        font_name = 'DejaVuSans'
        font_bold = 'DejaVuSans-Bold'
    except:
        # Fallback: Sử dụng Helvetica (có hỗ trợ Latin-1 extended)
        font_name = 'Helvetica'
        font_bold = 'Helvetica-Bold'

    # Create custom styles với font tiếng Việt
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontName=font_bold,
        fontSize=16,
        textColor=colors.HexColor('#1e3c72'),
        alignment=TA_CENTER,
        spaceAfter=20
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=font_bold,
        fontSize=14,
        textColor=colors.HexColor('#2a5298'),
        spaceAfter=12
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=11,
        spaceAfter=6
    )

    elems = []

    # Title
    elems.append(Paragraph("BÁO CÁO THẨM ĐỊNH PHƯƠNG ÁN SỬ DỤNG VỐN", title_style))
    elems.append(Spacer(1, 12))

    # Thông tin khách hàng
    elems.append(Paragraph("THÔNG TIN KHÁCH HÀNG", heading_style))
    customer_data = [
        ["Họ và tên:", state.get('name1', 'N/A')],
        ["Địa chỉ:", state.get('address', 'N/A')],
        ["Số điện thoại:", state.get('phone', 'N/A')],
        ["Email:", state.get('email', 'N/A')]
    ]

    customer_table = Table(customer_data, colWidths=[150, 350])
    customer_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3c72')),
        ('FONTNAME', (0, 0), (0, -1), font_bold),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elems.append(customer_table)
    elems.append(Spacer(1, 20))

    # Thông tin tài chính
    elems.append(Paragraph("THÔNG TIN TÀI CHÍNH", heading_style))
    financial_data = [
        ["Tổng nhu cầu vốn:", format_thousands(state.get('total_need', 0)) + " VND"],
        ["Vốn đối ứng:", format_thousands(state.get('own_capital', 0)) + " VND"],
        ["Số tiền vay:", format_thousands(state.get('loan_amount', 0)) + " VND"],
        ["Lãi suất:", f"{state.get('interest_rate', 0)}% /năm"],
        ["Thời hạn vay:", f"{state.get('term_months', 0)} tháng"],
    ]

    financial_table = Table(financial_data, colWidths=[150, 350])
    financial_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3c72')),
        ('FONTNAME', (0, 0), (0, -1), font_bold),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elems.append(financial_table)
    elems.append(Spacer(1, 20))

    # Các chỉ tiêu tài chính
    elems.append(Paragraph("CÁC CHỈ TIÊU ĐÁNH GIÁ", heading_style))

    indicator_data = []
    indicator_labels = {
        "monthly_payment": "Thanh toán hàng tháng",
        "total_payment": "Tổng thanh toán",
        "dsr": "Chỉ số DSR",
        "ltv": "Chỉ số LTV",
        "net_cashflow": "Dòng tiền ròng"
    }

    for k, v in indicators.items():
        label = indicator_labels.get(k, k)
        if v is None:
            disp = "N/A"
        elif k == "dsr":
            disp = f"{v:.2%}"
        elif k == "ltv":
            disp = f"{v:.2f}%"
        else:
            disp = format_thousands(v) + " VND"
        indicator_data.append([label + ":", disp])

    indicator_table = Table(indicator_data, colWidths=[150, 350])
    indicator_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3c72')),
        ('FONTNAME', (0, 0), (0, -1), font_bold),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
    ]))
    elems.append(indicator_table)
    elems.append(Spacer(1, 20))

    # Biểu đồ
    if chart_image_bytes:
        elems.append(Paragraph("BIỂU ĐỒ PHÂN TÍCH", heading_style))
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        f.write(chart_image_bytes)
        f.flush()
        elems.append(RLImage(f.name, width=450, height=280))

    doc.build(elems)

    with open(tmp.name, "rb") as f:
        return f.read()

# ==========================
# METRIC CARD COMPONENT
# ==========================
def metric_card(label, value, icon="💰"):
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size: 2em;">{icon}</div>
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)

# =============================================================
# BẮT ĐẦU ỨNG DỤNG STREAMLIT
# =============================================================
st.set_page_config(
    page_title="PASDV Analyzer", 
    layout="wide",
    page_icon="💼",
    initial_sidebar_state="expanded"
)

# Load Custom CSS
load_custom_css()

# Header với animation
st.markdown("""
<div class="main-title">
    <h1 style='text-align: center; color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);'>
        💼 PHÂN TÍCH PHƯƠNG ÁN SỬ DỤNG VỐN
    </h1>
    <p style='text-align: center; color: rgba(255,255,255,0.9); font-size: 1.2em;'>
        Ứng dụng hỗ trợ cán bộ tín dụng – Phiên bản hiện đại ❤️
    </p>
</div>
""", unsafe_allow_html=True)

# --------------------------
# Sidebar: API key Gemini
# --------------------------
with st.sidebar:
    st.markdown("### ⚙️ Cấu hình hệ thống")
    api_key = st.text_input("🔑 API Key Gemini", type="password")
    
    st.markdown("---")
    st.markdown("### 📤 Tùy chọn xuất dữ liệu")
    export_choice = st.selectbox(
        "Chọn định dạng",
        ["Không xuất", "Xuất Excel lịch trả nợ", "Xuất PDF thẩm định"]
    )
    
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <p style='color: rgba(255,255,255,0.8);'>🧡 Ứng dụng PASDV</p>
        <p style='color: rgba(255,255,255,0.6); font-size: 0.9em;'>
            Phiên bản hiện đại<br>
            Designed with ❤️
        </p>
    </div>
    """, unsafe_allow_html=True)

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
        "asset_address": "",
        "asset_type": "Nhà & đất",
        "asset_docs": "GCN QSDĐ",
        "monthly_income": 0,
        "monthly_expense": 0,
        "purpose": "Mua nhà"
    }

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

state = st.session_state["state"]

# =============================================================
# Giao diện chính — chia 2 cột
# =============================================================
left_col, right_col = st.columns([1, 3])

# ===========================
# LEFT: Upload & Reset
# ===========================
with left_col:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 📂 Upload hồ sơ")

    uploaded_file = st.file_uploader(
        "Kéo thả hoặc chọn file .docx", 
        type=["docx"],
        help="Tải lên file phương án vay vốn"
    )

    if uploaded_file:
        with st.spinner("🔄 Đang xử lý file..."):
            text = extract_text_from_docx(uploaded_file)
            parsed = extract_data_from_docx_text(text)

            for k, v in parsed.items():
                if v is not None:
                    state[k] = v

            st.success("✅ Trích xuất dữ liệu thành công!")
            with st.expander("📄 Xem nội dung file"):
                st.text_area("", text[:5000], height=200)

    st.markdown("---")

    if st.button("🔄 Reset dữ liệu", use_container_width=True):
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
            "asset_address": "",
            "asset_type": "Nhà & đất",
            "asset_docs": "GCN QSDĐ",
            "monthly_income": 0,
            "monthly_expense": 0,
            "purpose": "Mua nhà"
        }
        st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================
# RIGHT: Tabs
# =============================================================
with right_col:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    
    tabs = st.tabs([
        "👤 Định danh",
        "💰 Tài chính",
        "🏠 Tài sản",
        "📊 Tính toán",
        "📈 Biểu đồ",
        "🤖 AI",
        "💬 Chat",
        "📤 Xuất file"
    ])

    # ----------------------------------------------------------
    # Helper: Numeric with +/-
    # ----------------------------------------------------------
    def numeric_editor(label, key, step=1000000):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            current_val = state.get(key, 0)
            state[key] = st.number_input(
                label,
                value=int(current_val) if current_val else 0,
                min_value=0,
                step=step,
                key=f"num_{key}",
                format="%d"
            )
        with c2:
            if st.button("➕", key=f"plus_{key}", use_container_width=True):
                state[key] = state.get(key, 0) + step
                st.rerun()
        with c3:
            if st.button("➖", key=f"minus_{key}", use_container_width=True):
                state[key] = max(0, state.get(key, 0) - step)
                st.rerun()

    # =========================================================
    # TAB 1 – ĐỊNH DANH
    # =========================================================
    with tabs[0]:
        st.markdown("### 👤 Thông tin định danh khách hàng")
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            state["name1"] = st.text_input("👨‍💼 Họ và tên", value=state.get("name1", ""))
            state["address"] = st.text_input("🏡 Địa chỉ", value=state.get("address", ""))
        with col2:
            state["phone"] = st.text_input("📱 Số điện thoại", value=state.get("phone", ""))
            state["email"] = st.text_input("📧 Email", value=state.get("email", ""))

    # =========================================================
    # TAB 2 – TÀI CHÍNH
    # =========================================================
    with tabs[1]:
        st.markdown("### 💰 Thông tin tài chính & phương án vay")
        st.markdown("---")

        state["purpose"] = st.text_input("🎯 Mục đích vay", value=state.get("purpose", "Mua nhà"))

        numeric_editor("💵 Tổng nhu cầu vốn (VND)", "total_need", step=100000000)
        numeric_editor("💼 Vốn đối ứng (VND)", "own_capital", step=100000000)
        numeric_editor("🏦 Số tiền vay (VND)", "loan_amount", step=100000000)

        st.markdown("---")
        
        cA, cB = st.columns(2)
        with cA:
            state["interest_rate"] = st.number_input(
                "📊 Lãi suất (%/năm)", 
                value=float(state.get("interest_rate", 8.5)),
                min_value=0.0,
                max_value=100.0,
                step=0.1
            )
        with cB:
            state["term_months"] = st.number_input(
                "📅 Thời hạn vay (tháng)", 
                value=int(state.get("term_months", 60)), 
                min_value=1,
                max_value=360
            )
        
        # Thêm thông tin thu nhập chi phí
        st.markdown("---")
        st.markdown("#### 💳 Thu nhập & Chi phí")
        
        col1, col2 = st.columns(2)
        with col1:
            numeric_editor("📈 Thu nhập hàng tháng (VND)", "monthly_income", step=10000000)
        with col2:
            numeric_editor("📉 Chi phí hàng tháng (VND)", "monthly_expense", step=5000000)

    # =========================================================
    # TAB 3 – TÀI SẢN BẢO ĐẢM
    # =========================================================
    with tabs[2]:
        st.markdown("### 🏠 Tài sản bảo đảm")
        st.markdown("---")

        state["asset_type"] = st.text_input(
            "🏘️ Loại tài sản", 
            value=state.get("asset_type", "Nhà & đất")
        )
        
        numeric_editor("💎 Giá trị tài sản (VND)", "asset_value", step=100000000)

        st.markdown("---")
        
        state["asset_address"] = st.text_input(
            "📍 Địa chỉ tài sản", 
            value=state.get("asset_address", "")
        )
        state["asset_docs"] = st.text_input(
            "📋 Giấy tờ pháp lý", 
            value=state.get("asset_docs", "GCN QSDĐ")
        )

    # =========================================================
    # TAB 4 – TÍNH TOÁN
    # =========================================================
    with tabs[3]:
        st.markdown("### 📊 Kết quả tính toán chi tiết")
        st.markdown("---")

        indicators = compute_indicators(state)

        # Display metrics in cards
        col1, col2, col3 = st.columns(3)
        
        with col1:
            metric_card(
                "Thanh toán hàng tháng",
                format_thousands(indicators["monthly_payment"]) + " VND",
                "💵"
            )
        
        with col2:
            ltv_val = f"{indicators['ltv']:.2f}%" if indicators["ltv"] else "N/A"
            metric_card("LTV Ratio", ltv_val, "📊")
        
        with col3:
            dsr_val = f"{indicators['dsr']:.2%}" if indicators["dsr"] else "N/A"
            metric_card("DSR Ratio", dsr_val, "📈")

        st.markdown("---")
        st.markdown("#### 📋 Chi tiết các chỉ tiêu")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"**💰 Tổng thanh toán:** {format_thousands(indicators['total_payment'])} VND")
            st.info(f"**📊 DSR:** {f'{indicators["dsr"]:.2%}' if indicators['dsr'] else 'N/A'}")
            st.info(f"**💎 LTV:** {f'{indicators["ltv"]:.2f}%' if indicators['ltv'] else 'N/A'}")
        
        with col2:
            net_cf = indicators["net_cashflow"]
            if net_cf >= 0:
                st.success(f"**✅ Dòng tiền ròng:** +{format_thousands(net_cf)} VND")
            else:
                st.error(f"**❌ Dòng tiền ròng:** {format_thousands(net_cf)} VND")
            
            if indicators.get("dsr"):
                if indicators["dsr"] <= 0.4:
                    st.success("**✅ DSR:** Tốt (≤40%)")
                elif indicators["dsr"] <= 0.5:
                    st.warning("**⚠️ DSR:** Chấp nhận được (40-50%)")
                else:
                    st.error("**❌ DSR:** Rủi ro cao (>50%)")

        st.markdown("---")
        
        if st.button("📅 Tạo lịch trả nợ chi tiết", use_container_width=True):
            with st.spinner("Đang tạo lịch trả nợ..."):
                df_am = generate_amortization_schedule(
                    state.get("loan_amount", 0),
                    state.get("interest_rate", 0),
                    state.get("term_months", 0),
                )
                st.session_state["amortization"] = df_am
                st.success("✅ Đã tạo lịch trả nợ thành công!")

    # =========================================================
    # TAB 5 – BIỂU ĐỒ
    # =========================================================
    with tabs[4]:
        st.markdown("### 📈 Biểu đồ phân tích trực quan")
        st.markdown("---")

        df_am = st.session_state.get("amortization")

        if df_am is None:
            df_am = generate_amortization_schedule(
                state.get("loan_amount", 0),
                state.get("interest_rate", 0),
                state.get("term_months", 0),
            )

        if not df_am.empty:
            # Plotly interactive chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df_am["Month"], 
                y=df_am["Payment"],
                name="Thanh toán",
                line=dict(color='#667eea', width=3),
                fill='tonexty'
            ))
            
            fig.add_trace(go.Scatter(
                x=df_am["Month"], 
                y=df_am["Principal"],
                name="Gốc",
                line=dict(color='#764ba2', width=2)
            ))
            
            fig.add_trace(go.Scatter(
                x=df_am["Month"], 
                y=df_am["Interest"],
                name="Lãi",
                line=dict(color='#f093fb', width=2)
            ))
            
            fig.update_layout(
                title="Biểu đồ dòng tiền trả nợ theo tháng",
                xaxis_title="Tháng",
                yaxis_title="Số tiền (VND)",
                hovermode='x unified',
                template='plotly_white',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Pie chart for total payment breakdown
            total_principal = df_am["Principal"].sum()
            total_interest = df_am["Interest"].sum()
            
            fig2 = go.Figure(data=[go.Pie(
                labels=['Gốc', 'Lãi'],
                values=[total_principal, total_interest],
                hole=.4,
                marker_colors=['#667eea', '#f093fb']
            )])
            
            fig2.update_layout(
                title="Tỷ lệ Gốc/Lãi trong tổng thanh toán",
                height=400
            )
            
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("📊 Chưa có dữ liệu để hiển thị biểu đồ. Vui lòng nhập thông tin vay vốn.")

    # =========================================================
    # TAB 6 – PHÂN TÍCH AI
    # =========================================================
    with tabs[5]:
        st.markdown("### 🤖 Phân tích thông minh với Gemini AI")
        st.markdown("---")

        # Phân tích File Upload
        st.markdown("#### 📝 Phân tích dựa vào file upload")
        
        if st.button("🔍 Phân tích File", use_container_width=True):
            if not uploaded_file:
                st.warning("⚠️ Chưa có file upload!")
            else:
                uploaded_file.seek(0)
                raw_text = extract_text_from_docx(uploaded_file)

                prompt = (
                    "Hãy phân tích hồ sơ vay vốn dưới đây, tập trung vào rủi ro, "
                    "khả năng trả nợ, nguồn trả nợ, tài sản bảo đảm và kết luận đề xuất.\n\n"
                    f"--- DỮ LIỆU TỪ FILE UPLOAD ---\n{raw_text[:5000]}"
                )

                with st.spinner("🤖 Gemini đang phân tích..."):
                    ai_result = call_gemini(prompt, api_key)
                    st.markdown("**📊 Kết quả phân tích:**")
                    st.info(ai_result)

        st.markdown("---")

        # Phân tích dữ liệu đã nhập
        st.markdown("#### ✏️ Phân tích dựa vào dữ liệu đã chỉnh sửa")

        if st.button("🔍 Phân tích Dữ liệu", use_container_width=True):
            prompt2 = (
                "Hãy phân tích hồ sơ vay vốn dựa trên dữ liệu nhập liệu.\n\n"
                "--- DỮ LIỆU NHẬP LIỆU ---\n"
                f"{state}\n\n"
                "--- CÁC CHỈ TIÊU TÍNH TOÁN ---\n"
                f"{compute_indicators(state)}"
            )

            with st.spinner("🤖 Gemini đang phân tích..."):
                ai_result2 = call_gemini(prompt2, api_key)
                st.markdown("**📊 Kết quả phân tích:**")
                st.success(ai_result2)

    # =========================================================
    # TAB 7 – CHAT GEMINI
    # =========================================================
    with tabs[6]:
        st.markdown("### 💬 Chat trực tiếp với Gemini AI")
        st.markdown("---")

        # Chat input
        chat_input = st.text_input("💭 Nhập câu hỏi của bạn:", key="chat_input")

        col1, col2 = st.columns([3, 1])
        with col1:
            send_btn = st.button("📤 Gửi", use_container_width=True)
        with col2:
            clear_btn = st.button("🗑️ Xóa", use_container_width=True)

        if send_btn and chat_input:
            st.session_state["chat_history"].append(("User", chat_input))
            with st.spinner("Đang xử lý..."):
                reply = call_gemini(chat_input, api_key)
                st.session_state["chat_history"].append(("Gemini", reply))
            st.rerun()

        if clear_btn:
            st.session_state["chat_history"] = []
            st.rerun()

        # Display chat history
        st.markdown("---")
        st.markdown("#### 💬 Lịch sử hội thoại")
        
        for role, msg in reversed(st.session_state["chat_history"]):
            if role == "User":
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 15px; border-radius: 15px; margin: 10px 0; color: white;'>
                    <strong>🧑 Bạn:</strong> {msg}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='background: #f7fafc; padding: 15px; border-radius: 15px; 
                            margin: 10px 0; border-left: 4px solid #667eea;'>
                    <strong>🤖 Gemini:</strong> {msg}
                </div>
                """, unsafe_allow_html=True)

    # =========================================================
    # TAB 8 – XUẤT FILE
    # =========================================================
    with tabs[7]:
        st.markdown("### 📤 Xuất file báo cáo")
        st.markdown("---")

        df_am = st.session_state.get("amortization")

        if df_am is None:
            df_am = generate_amortization_schedule(
                state.get("loan_amount", 0),
                state.get("interest_rate", 0),
                state.get("term_months", 0),
            )

        col1, col2 = st.columns(2)

        # Xuất Excel
        with col1:
            st.markdown("#### 📗 Xuất Excel")
            st.info("Tải về lịch trả nợ chi tiết dạng Excel")
            
            if st.button("⬇️ Tải Excel", use_container_width=True):
                xls_bytes = df_to_excel_bytes(df_am)
                st.download_button(
                    "💾 Lưu file Excel",
                    data=xls_bytes,
                    file_name=f"lich_tra_no_{datetime.date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        # Xuất PDF
        with col2:
            st.markdown("#### 📕 Xuất PDF")
            st.info("Tải về báo cáo thẩm định đầy đủ")
            
            if st.button("⬇️ Tải PDF", use_container_width=True):
                indicators = compute_indicators(state)

                # Tạo biểu đồ cho PDF
                fig2, ax2 = plt.subplots(figsize=(8, 3))
                ax2.plot(df_am["Month"], df_am["Payment"])
                ax2.set_title("Biểu đồ nghĩa vụ trả nợ")
                buf2 = io.BytesIO()
                fig2.savefig(buf2, format="png", bbox_inches="tight")
                pdf_chart_bytes = buf2.getvalue()

                pdf_data = create_pdf_report(state, indicators, chart_image_bytes=pdf_chart_bytes)

                st.download_button(
                    "💾 Lưu file PDF",
                    data=pdf_data,
                    file_name=f"bao_cao_tham_dinh_{datetime.date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # Preview table
        if not df_am.empty:
            st.markdown("#### 📊 Xem trước lịch trả nợ")
            st.dataframe(
                df_am.head(12),
                use_container_width=True,
                hide_index=True
            )

    st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; padding: 20px; color: white;'>
    <p>Made with ❤️ for Agribank | © 2024 PASDV Analyzer</p>
</div>
""", unsafe_allow_html=True)
