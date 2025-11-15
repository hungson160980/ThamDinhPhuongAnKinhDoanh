# main.py
"""
PASDV Analyzer - single-file Streamlit app
Features:
- Upload .docx and heuristic extraction (tuned to PASDV.docx sample)
- Editable inputs with +/- buttons; thousand separator uses '.'
- Tabs: Identification, Finance, Collateral, Calculations, Charts, AI Analysis, Chatbox, Export
- Two AI analyses (from uploaded file, from adjusted inputs) via gemini-2.5-flash wrapper
- Chatbox with Gemini and Clear button
- Amortization schedule generation, Excel export, DOCX export (if python-docx installed), PDF export (if reportlab installed)
- Safe imports and helpful debug outputs
Author: Generated for Huynh
"""

from __future__ import annotations
import io
import re
import math
import json
import datetime
import tempfile
from typing import Dict, Any, Optional

import pandas as pd
import streamlit as st

# ----------------------------
# Safe imports for optional libs
# ----------------------------
# python-docx for reading & writing .docx
try:
    from docx import Document as DocxReader
except Exception:
    DocxReader = None

# python-docx writer (same as above; we use Document for writing if available)
try:
    import docx
    DocxWriter = docx.Document
except Exception:
    DocxWriter = None

# matplotlib for charts
try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

# requests for Gemini wrapper
try:
    import requests
except Exception:
    requests = None

# reportlab for PDF export
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet
except Exception:
    SimpleDocTemplate = None

# openpyxl provided via pandas engine when writing Excel

# ----------------------------
# Configuration
# ----------------------------
GEMINI_API_URL = "https://api.example.com/gemini"  # <-- Replace with real endpoint
GEMINI_MODEL = "gemini-2.5-flash"

# ----------------------------
# Utilities: formatting & parsing
# ----------------------------
def format_thousands_dot(x: Optional[float]) -> str:
    """Format as integer with '.' thousands separator."""
    if x is None:
        return ""
    try:
        # treat NaN
        if isinstance(x, float) and math.isnan(x):
            return ""
        v = float(x)
        s = f"{v:,.0f}"
        return s.replace(",", ".")
    except Exception:
        return str(x)

def format_number_locale(x: Optional[float], decimals: int = 2) -> str:
    if x is None:
        return ""
    try:
        if decimals == 0:
            return format_thousands_dot(x)
        s = f"{x:,.{decimals}f}"
        # swap thousands/comma to '.' thousands and ',' decimal
        s = s.replace(",", "_").replace(".", ",").replace("_", ".")
        return s
    except Exception:
        return str(x)

def vnd_to_float(s: Optional[str]) -> float:
    """Parse Vietnamese money strings like '5.000.000.000 đồng'."""
    if s is None:
        return 0.0
    s = str(s).strip()
    s = s.replace("đồng", "").replace("VND", "").replace("vnđ", "").replace("₫", "")
    s = s.replace(" ", "")
    # Handle formats
    if "." in s and "," in s:
        # e.g. 1.234.567,89 -> remove dots, replace comma with dot
        s = s.replace(".", "").replace(",", ".")
    else:
        # remove non-numeric separators
        s = s.replace(".", "").replace(",", "")
    s = re.sub(r"[^\d\.\-]", "", s)
    try:
        return float(s) if s not in ("", ".", "-") else 0.0
    except Exception:
        return 0.0

def percent_to_float(s: Optional[str]) -> float:
    if s is None:
        return 0.0
    s = str(s).strip().replace(",", ".")
    m = re.search(r"(\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else 0.0

# ----------------------------
# DOCX extraction heuristics (tuned to PASDV.docx sample)
# ----------------------------
def extract_text_from_docx_bytes(file_bytes: bytes) -> str:
    """Return joined paragraphs from docx bytes or empty string if cannot read."""
    if DocxReader is None:
        return ""
    bio = io.BytesIO(file_bytes)
    doc = DocxReader(bio)
    paras = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            paras.append(t)
    return "\n".join(paras)

def extract_fields_from_text(text: str) -> Dict[str, Any]:
    """Heuristic extraction to map fields from PASDV doc to structured data."""
    defaults = {
        "name": "",
        "cccd": "",
        "address": "",
        "phone": "",
        "email": "",
        "purpose": "",
        "total_need": 0.0,
        "own_capital": 0.0,
        "loan_amount": 0.0,
        "interest_rate": 0.0,
        "term_months": 0,
        "project_income_month": 0.0,
        "salary_income_month": 0.0,
        "total_income_month": 0.0,
        "monthly_expense": 0.0,
        "collateral_value": 0.0
    }
    if not text:
        return defaults
    t = text.replace("\r", "\n")
    # Name: look for "Họ và tên: X" — pick first occurrence
    m = re.search(r"Họ\s+và\s+tên\s*[:\-–]?\s*([A-Za-zÀ-ỹ\s]+)", t, flags=re.IGNORECASE)
    if m:
        defaults["name"] = m.group(1).strip()
    # cccd/cmnd
    m = re.search(r"(?:CMND|CCCD|CMND/CCCD|CMND\/CCCD).*?[:\-–]?\s*([0-9]{9,12})", t, flags=re.IGNORECASE)
    if m:
        defaults["cccd"] = m.group(1).strip()
    # phone
    m = re.search(r"Số\s*điện\s*thoại\s*[:\-–]?\s*(0\d{8,10})", t, flags=re.IGNORECASE)
    if m:
        defaults["phone"] = m.group(1).strip()
    else:
        m = re.search(r"\b(0\d{8,10})\b", t)
        if m:
            defaults["phone"] = m.group(1)
    # email
    m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", t)
    if m:
        defaults["email"] = m.group(0)
    # address
    m = re.search(r"Nơi\s*cư\s*trú\s*[:\-–]?\s*([^\n]+)", t, flags=re.IGNORECASE)
    if m:
        defaults["address"] = m.group(1).strip()
    # purpose
    m = re.search(r"Mục\s*đích\s*vay\s*[:\-–]?\s*([^\n]+)", t, flags=re.IGNORECASE)
    if m:
        defaults["purpose"] = m.group(1).strip()
    # total need
    m = re.search(r"Tổng\s*nhu\s*cầu\s*vốn\s*[:\-–]?\s*([\d\.,\s]+)\s*đồng?", t, flags=re.IGNORECASE)
    if m:
        defaults["total_need"] = vnd_to_float(m.group(1))
    # own capital
    m = re.search(r"Vốn\s*đối\s*ứng.*?([\d\.,\s]+)\s*đồng?", t, flags=re.IGNORECASE)
    if m:
        defaults["own_capital"] = vnd_to_float(m.group(1))
    # loan amount
    m = re.search(r"Vốn\s*vay.*?([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
    if m:
        defaults["loan_amount"] = vnd_to_float(m.group(1))
    # interest rate
    m = re.search(r"Lãi\s*suất\s*[:\-–]?\s*([\d\.,]+)\s*%/?năm?", t, flags=re.IGNORECASE)
    if m:
        defaults["interest_rate"] = percent_to_float(m.group(1))
    else:
        m = re.search(r"(\d+[.,]?\d*)\s*%/năm", t)
        if m:
            defaults["interest_rate"] = percent_to_float(m.group(1))
    # term months
    m = re.search(r"Thời\s*hạn\s*vay\s*[:\-–]?\s*(\d+)\s*tháng", t, flags=re.IGNORECASE)
    if m:
        defaults["term_months"] = int(m.group(1))
    else:
        m = re.search(r"Thời\s*hạn\s*vay.*?(\d+)\s*năm", t, flags=re.IGNORECASE)
        if m:
            defaults["term_months"] = int(m.group(1)) * 12
    # project income (30.000.000 đồng/tháng)
    m = re.search(r"([\d\.,\s]+)\s*đồng\s*/\s*tháng", t)
    if m:
        defaults["project_income_month"] = vnd_to_float(m.group(1))
    # salary incomes lines
    m = re.search(r"Thu\s*nhập.*?lương.*?[:\-–]?\s*([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
    if m:
        defaults["salary_income_month"] = vnd_to_float(m.group(1))
    # total income
    m = re.search(r"Tổng\s*thu\s*nhập.*?([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
    if m:
        defaults["total_income_month"] = vnd_to_float(m.group(1))
    else:
        defaults["total_income_month"] = defaults["salary_income_month"] + defaults["project_income_month"]
    # monthly expense
    m = re.search(r"Tổng\s*chi\s*phí\s*hàng\s*tháng\s*[:\-–]?\s*([\d\.,\s]+)\s*(?:đồng)?", t, flags=re.IGNORECASE)
    if m:
        defaults["monthly_expense"] = vnd_to_float(m.group(1))
    # collateral value
    m = re.search(r"Giá\s*trị(?:.*?nhà.*|).*?([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
    if m:
        defaults["collateral_value"] = vnd_to_float(m.group(1))
    else:
        m = re.search(r"Tài\s*sản[^\n]{0,80}Giá\s*trị\s*[:\-–]?\s*([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
        if m:
            defaults["collateral_value"] = vnd_to_float(m.group(1))
    # final sanitize
    for k in defaults:
        if defaults[k] is None:
            defaults[k] = "" if isinstance(defaults[k], str) else 0.0
    return defaults

# ----------------------------
# Financial: PMT and schedule
# ----------------------------
def annuity_payment(principal: float, annual_rate_pct: float, months: int) -> float:
    try:
        p = float(principal)
        n = int(months)
        r = float(annual_rate_pct) / 100.0 / 12.0
        if n <= 0 or p <= 0:
            return 0.0
        if r == 0:
            return p / n
        payment = p * r / (1 - (1 + r) ** (-n))
        return float(payment)
    except Exception:
        return 0.0

def amortization_schedule(principal: float, annual_rate_pct: float, months: int, start_date: Optional[datetime.date] = None) -> pd.DataFrame:
    if start_date is None:
        start_date = datetime.date.today()
    schedule = []
    if months <= 0 or principal <= 0:
        return pd.DataFrame(columns=["Month", "Date", "Payment", "Principal", "Interest", "Remaining"])
    payment = annuity_payment(principal, annual_rate_pct, months)
    balance = float(principal)
    monthly_rate = float(annual_rate_pct) / 100.0 / 12.0
    for i in range(1, months + 1):
        interest = balance * monthly_rate
        principal_paid = payment - interest
        if principal_paid > balance:
            principal_paid = balance
            payment = interest + principal_paid
        balance = max(0.0, balance - principal_paid)
        pay_date = (pd.Timestamp(start_date) + pd.DateOffset(months=i)).strftime("%Y-%m-%d")
        schedule.append({
            "Month": i,
            "Date": pay_date,
            "Payment": round(payment, 0),
            "Principal": round(principal_paid, 0),
            "Interest": round(interest, 0),
            "Remaining": round(balance, 0)
        })
    df = pd.DataFrame(schedule)
    return df

def compute_indicators(inputs: Dict[str, Any]) -> Dict[str, Any]:
    loan = float(inputs.get("loan_amount", 0.0) or 0.0)
    rate = float(inputs.get("interest_rate", 0.0) or 0.0)
    term = int(inputs.get("term_months", 0) or 0)
    income = float(inputs.get("total_income_month", 0.0) or 0.0)
    expense = float(inputs.get("monthly_expense", 0.0) or 0.0)
    collateral = float(inputs.get("collateral_value", 0.0) or 0.0)
    own = float(inputs.get("own_capital", 0.0) or 0.0)
    pmt = annuity_payment(loan, rate, term)
    total_pay = pmt * max(1, term)
    dsr = pmt / income if income > 0 else float("nan")
    ltv = (loan / collateral) if collateral > 0 else float("nan")
    net_cf = income - expense - pmt
    e_over_c = own / (inputs.get("total_need", 1.0) or 1.0) if inputs.get("total_need", 0.0) > 0 else float("nan")
    coverage = collateral / max(1e-9, loan) if loan > 0 else float("nan")
    # simple scoring
    score = 0.0
    try:
        if not math.isnan(dsr):
            score += max(0.0, 1.0 - min(1.0, dsr)) * 0.3
        if not math.isnan(ltv):
            score += max(0.0, 1.0 - min(1.0, ltv)) * 0.3
        if not math.isnan(e_over_c):
            score += min(1.0, e_over_c / 0.3) * 0.2
        if not math.isnan(coverage):
            score += min(1.0, coverage / 1.5) * 0.2
    except Exception:
        pass
    return {
        "PMT": pmt,
        "TotalPayment": total_pay,
        "DSR": dsr,
        "LTV": ltv,
        "NetCashFlow": net_cf,
        "EquityOverNeed": e_over_c,
        "Coverage": coverage,
        "Score": round(score, 3)
    }

# ----------------------------
# Gemini wrapper (placeholder)
# ----------------------------
def call_gemini_api(prompt: str, api_key: str, model: str = GEMINI_MODEL, max_tokens: int = 512) -> str:
    if requests is None:
        return "Requests library is not installed; Gemini calls disabled."
    if not api_key:
        return "No API key provided."
    payload = {"model": model, "prompt": prompt, "max_tokens": max_tokens}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        r = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            try:
                j = r.json()
                # attempt common fields
                for k in ("text", "content", "output", "response"):
                    if k in j:
                        return j[k] or str(j)
                if "choices" in j and isinstance(j["choices"], list) and j["choices"]:
                    ch = j["choices"][0]
                    if isinstance(ch, dict):
                        return ch.get("text") or ch.get("message", {}).get("content", "") or str(ch)
                return str(j)
            except Exception:
                return r.text
        else:
            return f"Gemini API error {r.status_code}: {r.text}"
    except Exception as e:
        return f"Exception calling Gemini: {e}"

# ----------------------------
# Export helpers
# ----------------------------
def df_to_excel_bytes(df: pd.DataFrame, info: Dict[str, Any] = None, metrics: Dict[str, Any] = None) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Amortization", index=False)
        if info is not None:
            pd.DataFrame([info]).to_excel(writer, sheet_name="Info", index=False)
        if metrics is not None:
            pd.DataFrame([metrics]).to_excel(writer, sheet_name="Metrics", index=False)
    buf.seek(0)
    return buf.read()

def create_pdf_report_bytes(inputs: Dict[str, Any], metrics: Dict[str, Any], schedule: pd.DataFrame, chart_bytes: Optional[bytes], analysis_text: str = "") -> bytes:
    if SimpleDocTemplate is None:
        return b""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []
    elems.append(Paragraph("BÁO CÁO THẨM ĐỊNH PHƯƠNG ÁN SỬ DỤNG VỐN", styles["Title"]))
    elems.append(Spacer(1, 6))
    elems.append(Paragraph(f"Khách hàng: {inputs.get('name','')}", styles["Normal"]))
    elems.append(Paragraph(f"Mục đích vay: {inputs.get('purpose','')}", styles["Normal"]))
    elems.append(Spacer(1, 6))
    elems.append(Paragraph("Các chỉ tiêu chính:", styles["Heading2"]))
    for k, v in metrics.items():
        val = v
        if isinstance(v, float):
            elems.append(Paragraph(f"{k}: {format_number_locale(v)}", styles["Normal"]))
        else:
            elems.append(Paragraph(f"{k}: {str(v)}", styles["Normal"]))
    elems.append(Spacer(1, 6))
    if chart_bytes:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        f.write(chart_bytes)
        f.flush()
        elems.append(RLImage(f.name, width=400, height=200))
        elems.append(Spacer(1, 6))
    if analysis_text:
        elems.append(Paragraph("Phân tích AI:", styles["Heading2"]))
        elems.append(Paragraph(analysis_text, styles["Normal"]))
    doc.build(elems)
    buf.seek(0)
    return buf.read()

def export_docx_bytes(inputs: Dict[str, Any], metrics: Dict[str, Any], schedule: pd.DataFrame, analysis_text: str = "") -> bytes:
    if DocxWriter is None:
        return b""
    doc = DocxWriter()
    doc.add_heading("BÁO CÁO THẨM ĐỊNH PHƯƠNG ÁN SỬ DỤNG VỐN", level=1)
    doc.add_paragraph(f"Khách hàng: {inputs.get('name','')}")
    doc.add_paragraph(f"Mục đích: {inputs.get('purpose','')}")
    doc.add_paragraph("Chỉ tiêu:")
    for k, v in metrics.items():
        doc.add_paragraph(f"- {k}: {format_number_locale(v)}")
    doc.add_paragraph()
    doc.add_paragraph("Kế hoạch trả nợ (5 kỳ đầu):")
    table = doc.add_table(rows=1, cols=6)
    hdr = table.rows[0].cells
    hdr[0].text = "Kỳ"
    hdr[1].text = "Date"
    hdr[2].text = "Payment"
    hdr[3].text = "Principal"
    hdr[4].text = "Interest"
    hdr[5].text = "Remaining"
    for _, row in schedule.head(5).iterrows():
        r = table.add_row().cells
        r[0].text = str(int(row["Month"]))
        r[1].text = str(row["Date"])
        r[2].text = format_thousands_dot(row["Payment"])
        r[3].text = format_thousands_dot(row["Principal"])
        r[4].text = format_thousands_dot(row["Interest"])
        r[5].text = format_thousands_dot(row["Remaining"])
    if analysis_text:
        doc.add_page_break()
        doc.add_heading("Phân tích AI", level=2)
        doc.add_paragraph(analysis_text)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()

# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="PASDV Analyzer", layout="wide")
st.title("PASDV Analyzer — Phân tích Phương Án Sử Dụng Vốn")
st.markdown("Upload file .docx mẫu (PASDV) → trích xuất → chỉnh sửa → tính toán → AI → xuất")

# Sidebar
with st.sidebar:
    st.header("Cấu hình")
    api_key = st.text_input("API Key Gemini (gemini-2.5-flash)", type="password")
    st.write("GEMINI endpoint:", GEMINI_API_URL)
    st.markdown("---")
    st.write("Xuất mặc định:")
    default_export = st.selectbox("Định dạng khi tải", ["PDF", "DOCX", "Excel"])
    st.markdown("---")
    st.write("Debug / Thông tin")
    if DocxReader is None:
        st.error("python-docx không cài — upload .docx sẽ không hoạt động. Thêm 'python-docx' vào requirements.txt")
    if requests is None:
        st.warning("requests không cài — tính năng AI sẽ không hoạt động.")
    if plt is None:
        st.warning("matplotlib không cài — biểu đồ sẽ không hiển thị.")
    if SimpleDocTemplate is None:
        st.info("reportlab không cài — xuất PDF bị tắt.")
    if DocxWriter is None:
        st.info("python-docx writer không cài — xuất DOCX bị tắt.")

# Initialize session state
if "inputs" not in st.session_state:
    st.session_state["inputs"] = {
        "name": "",
        "cccd": "",
        "address": "",
        "phone": "",
        "email": "",
        "purpose": "",
        "total_need": 0.0,
        "own_capital": 0.0,
        "loan_amount": 0.0,
        "interest_rate": 8.5,
        "term_months": 60,
        "project_income_month": 0.0,
        "salary_income_month": 0.0,
        "total_income_month": 0.0,
        "monthly_expense": 0.0,
        "collateral_value": 0.0,
        "tong_no_hien_tai": 0.0
    }
if "raw_text" not in st.session_state:
    st.session_state["raw_text"] = ""
if "amortization" not in st.session_state:
    st.session_state["amortization"] = pd.DataFrame()
if "analysis_file" not in st.session_state:
    st.session_state["analysis_file"] = ""
if "analysis_inputs" not in st.session_state:
    st.session_state["analysis_inputs"] = ""
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Upload column
left_col, right_col = st.columns([1, 3])
with left_col:
    st.header("Upload file (.docx)")
    uploaded = st.file_uploader("Upload PASDV.docx (mẫu)", type=["docx"])
    if uploaded:
        try:
            uploaded_bytes = uploaded.read()
            raw = extract_text_from_docx_bytes(uploaded_bytes)
            st.session_state["raw_text"] = raw
            st.success("Đã đọc file. Kiểm tra tab '1. Identification' và 'Debug' nếu cần.")
            parsed = extract_fields_from_text(raw)
            # merge parsed values into inputs (only if inputs empty or zero)
            for k, v in parsed.items():
                if k in st.session_state["inputs"]:
                    cur = st.session_state["inputs"][k]
                    if (isinstance(cur, (int, float)) and (cur == 0 or cur is None)) or (isinstance(cur, str) and cur == ""):
                        st.session_state["inputs"][k] = v
            # immediate debug
            st.write("📄 Raw text length:", len(raw))
            if len(raw) < 50:
                st.warning("File trích xuất ra quá ngắn — kiểm tra file hoặc yêu cầu python-docx.")
            st.text_area("Preview raw text", raw[:4000], height=200)
            st.write("🎯 Parsed fields:", parsed)
        except Exception as e:
            st.error(f"Lỗi khi đọc file: {e}")

    st.markdown("---")
    if st.button("Reset toàn bộ"):
        for k in st.session_state["inputs"]:
            st.session_state["inputs"][k] = "" if isinstance(st.session_state["inputs"][k], str) else 0.0
        st.session_state["raw_text"] = ""
        st.session_state["amortization"] = pd.DataFrame()
        st.session_state["analysis_file"] = ""
        st.session_state["analysis_inputs"] = ""
        st.session_state["chat_history"] = []
        st.experimental_rerun()

# Tabs
tabs = right_col.tabs([
    "1. Identification",
    "2. Finance",
    "3. Collateral",
    "4. Calculations",
    "5. Charts",
    "6. AI Analysis",
    "7. Chatbox",
    "8. Export",
    "Debug"
])

# Tab 1: Identification
with tabs[0]:
    st.header("1. Identification")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Họ và tên", key="ui_name", value=st.session_state["inputs"]["name"], on_change=lambda: st.session_state["inputs"].update({"name": st.session_state.get("ui_name", "")}))
        st.text_input("CCCD/CMND", key="ui_cccd", value=st.session_state["inputs"]["cccd"], on_change=lambda: st.session_state["inputs"].update({"cccd": st.session_state.get("ui_cccd", "")}))
        st.text_input("Địa chỉ", key="ui_address", value=st.session_state["inputs"]["address"], on_change=lambda: st.session_state["inputs"].update({"address": st.session_state.get("ui_address", "")}))
    with c2:
        st.text_input("Số điện thoại", key="ui_phone", value=st.session_state["inputs"]["phone"], on_change=lambda: st.session_state["inputs"].update({"phone": st.session_state.get("ui_phone", "")}))
        st.text_input("Email", key="ui_email", value=st.session_state["inputs"]["email"], on_change=lambda: st.session_state["inputs"].update({"email": st.session_state.get("ui_email", "")}))
        st.text_input("Mục đích vay", key="ui_purpose", value=st.session_state["inputs"]["purpose"], on_change=lambda: st.session_state["inputs"].update({"purpose": st.session_state.get("ui_purpose", "")}))

# helper widget: money field with +/- and '.' formatting
def money_widget(label: str, key: str, step: float = 1_000_000.0):
    a, b, c = st.columns([3, 1, 1])
    current = st.session_state["inputs"].get(key, 0.0)
    display = format_thousands_dot(current) if current else ""
    with a:
        txt = st.text_input(label, value=display, key=f"txt_{key}")
        parsed = vnd_to_float(txt)
        st.session_state["inputs"][key] = parsed
    with b:
        if st.button("+", key=f"plus_{key}"):
            st.session_state["inputs"][key] = st.session_state["inputs"].get(key, 0.0) + step
    with c:
        if st.button("-", key=f"minus_{key}"):
            st.session_state["inputs"][key] = max(0.0, st.session_state["inputs"].get(key, 0.0) - step)

def percent_widget(label: str, key: str):
    a, b = st.columns([3, 1])
    current = st.session_state["inputs"].get(key, 0.0)
    with a:
        txt = st.text_input(label, value=f"{current:.2f}".replace(".", ","), key=f"pct_{key}")
        st.session_state["inputs"][key] = percent_to_float(txt)
    with b:
        st.write("")

# Tab 2: Finance
with tabs[1]:
    st.header("2. Finance")
    money_widget("Tổng nhu cầu vốn (VND)", "total_need", step=100_000_000)
    money_widget("Vốn đối ứng (VND)", "own_capital", step=50_000_000)
    money_widget("Số tiền vay (VND)", "loan_amount", step=100_000_000)
    percent_widget("Lãi suất (%/năm)", "interest_rate")
    colA, colB = st.columns(2)
    with colA:
        st.number_input("Thời hạn vay (tháng)", min_value=1, max_value=600, value=int(st.session_state["inputs"].get("term_months", 60)), key="ui_term", on_change=lambda: st.session_state["inputs"].update({"term_months": int(st.session_state.get("ui_term", 60))}))
    with colB:
        st.write("Tổng nhu cầu hiện:", format_thousands_dot(st.session_state["inputs"].get("total_need", 0.0)))
        st.write("Đối ứng + Vay:", format_thousands_dot(st.session_state["inputs"].get("own_capital", 0.0) + st.session_state["inputs"].get("loan_amount", 0.0)))
        if abs((st.session_state["inputs"].get("own_capital", 0.0) + st.session_state["inputs"].get("loan_amount", 0.0)) - st.session_state["inputs"].get("total_need", 0.0)) > 1.0:
            st.warning("Tổng vốn đối ứng + vay khác Tổng nhu cầu vốn. Kiểm tra dữ liệu.")

# Tab 3: Collateral
with tabs[2]:
    st.header("3. Collateral")
    money_widget("Giá trị tài sản bảo đảm (VND)", "collateral_value", step=100_000_000)
    st.text_input("Địa chỉ TSĐB", key="ui_coll_addr", value=st.session_state["inputs"].get("collateral_address",""), on_change=lambda: st.session_state["inputs"].update({"collateral_address": st.session_state.get("ui_coll_addr","")}))
    st.text_input("Giấy tờ pháp lý", key="ui_coll_docs", value=st.session_state["inputs"].get("collateral_docs",""), on_change=lambda: st.session_state["inputs"].update({"collateral_docs": st.session_state.get("ui_coll_docs","")}))

# Tab 4: Calculations
with tabs[3]:
    st.header("4. Calculations")
    # ensure total income
    if st.session_state["inputs"].get("total_income_month", 0.0) == 0.0:
        st.session_state["inputs"]["total_income_month"] = st.session_state["inputs"].get("salary_income_month", 0.0) + st.session_state["inputs"].get("project_income_month", 0.0)
    st.write("Tổng thu nhập hàng tháng:", format_thousands_dot(st.session_state["inputs"].get("total_income_month", 0.0)))
    metrics = compute_indicators(st.session_state["inputs"])
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Thanh toán hàng tháng (PMT)", format_thousands_dot(metrics["PMT"]))
        st.metric("Tổng trả (ước tính)", format_thousands_dot(metrics["TotalPayment"]))
    with col2:
        st.metric("DSR (<=80%)", f"{metrics['DSR']*100:.2f}%" if not math.isnan(metrics["DSR"]) else "N/A")
        st.metric("LTV (<=80%)", f"{metrics['LTV']*100:.2f}%" if not math.isnan(metrics["LTV"]) else "N/A")
    with col3:
        st.metric("Net cashflow", format_thousands_dot(metrics["NetCashFlow"]))
        st.metric("Score", str(metrics["Score"]))
    st.markdown("**Ghi chú:** Phương pháp annuity (trả đều).")
    if st.button("Tạo lịch trả nợ"):
        schedule = amortization_schedule(
            principal=st.session_state["inputs"].get("loan_amount", 0.0),
            annual_rate_pct=st.session_state["inputs"].get("interest_rate", 0.0),
            months=int(st.session_state["inputs"].get("term_months", 60)),
            start_date=datetime.date.today()
        )
        st.session_state["amortization"] = schedule
        st.success("Đã tạo lịch trả nợ (amortization). Sang tab 'Charts' hoặc 'Export' để tải về.")

# Tab 5: Charts
with tabs[4]:
    st.header("5. Charts")
    schedule = st.session_state.get("amortization")
    if schedule is None or schedule.empty:
        schedule = amortization_schedule(
            principal=st.session_state["inputs"].get("loan_amount", 0.0),
            annual_rate_pct=st.session_state["inputs"].get("interest_rate", 0.0),
            months=int(st.session_state["inputs"].get("term_months", 60))
        )
    if plt is None:
        st.warning("matplotlib chưa cài: không thể vẽ biểu đồ.")
    else:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(schedule["Month"], schedule["Payment"], label="Payment")
        ax.plot(schedule["Month"], schedule["Principal"], label="Principal")
        ax.plot(schedule["Month"], schedule["Interest"], label="Interest")
        ax.set_xlabel("Kỳ")
        ax.set_ylabel("VND")
        ax.legend()
        st.pyplot(fig)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        chart_png = buf.getvalue()
        st.session_state["chart_png"] = chart_png

# Tab 6: AI Analysis (File & Inputs)
with tabs[5]:
    st.header("6. AI Analysis (Gemini)")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("A. Phân tích từ File Upload (nguồn: file)")
        st.markdown("Nguồn dữ liệu: file .docx upload")
        if st.button("Phân tích từ File Upload"):
            raw = st.session_state.get("raw_text", "")
            if not raw:
                st.warning("Chưa upload file hoặc dữ liệu trống.")
            else:
                prompt = f"Bạn là chuyên viên thẩm định tín dụng. Phân tích (ngắn gọn) phương án vay theo dữ liệu dưới đây. Trả lời gồm: tóm tắt, rủi ro chính, khả năng trả nợ, đề xuất.\n\n{raw[:6000]}"
                with st.spinner("Gọi Gemini..."):
                    out = call_gemini_api(prompt, api_key or "", model=GEMINI_MODEL, max_tokens=600)
                    st.session_state["analysis_file"] = out
        if st.session_state.get("analysis_file"):
            st.text_area("Kết quả phân tích (File)", st.session_state.get("analysis_file"), height=250)
    with c2:
        st.subheader("B. Phân tích từ dữ liệu đã chỉnh (nguồn: GUI)")
        st.markdown("Nguồn dữ liệu: dữ liệu người dùng nhập/chỉnh sửa")
        if st.button("Phân tích từ dữ liệu GUI"):
            inputs_snapshot = st.session_state["inputs"].copy()
            metrics_snapshot = compute_indicators(inputs_snapshot)
            prompt2 = f"Bạn là chuyên viên thẩm định tín dụng. Phân tích dựa trên dữ liệu và các chỉ số sau:\n{json.dumps(inputs_snapshot, ensure_ascii=False)}\n{json.dumps(metrics_snapshot, ensure_ascii=False)}"
            with st.spinner("Gọi Gemini..."):
                out2 = call_gemini_api(prompt2, api_key or "", model=GEMINI_MODEL, max_tokens=600)
                st.session_state["analysis_inputs"] = out2
        if st.session_state.get("analysis_inputs"):
            st.text_area("Kết quả phân tích (GUI)", st.session_state.get("analysis_inputs"), height=250)

# Tab 7: Chatbox
with tabs[6]:
    st.header("7. Chatbox Gemini")
    q_col, btn_col = st.columns([4,1])
    with q_col:
        chat_q = st.text_input("Nhập câu hỏi cho Gemini về hồ sơ này", key="chat_question")
    with btn_col:
        if st.button("Gửi câu hỏi"):
            if not chat_q:
                st.warning("Nhập câu hỏi trước khi gửi.")
            else:
                st.session_state["chat_history"].append({"role":"user","text":chat_q})
                context = st.session_state.get("raw_text") or json.dumps(st.session_state["inputs"], ensure_ascii=False)
                prompt_chat = f"Context: {context[:3000]}\nUser: {chat_q}"
                with st.spinner("Gọi Gemini..."):
                    resp = call_gemini_api(prompt_chat, api_key or "", model=GEMINI_MODEL, max_tokens=400)
                    st.session_state["chat_history"].append({"role":"assistant","text":resp})
    if st.button("Xóa chat"):
        st.session_state["chat_history"] = []
    st.markdown("### Lịch sử chat")
    for msg in st.session_state["chat_history"]:
        if msg["role"] == "user":
            st.markdown(f"**Bạn:** {msg['text']}")
        else:
            st.markdown(f"**Gemini:** {msg['text']}")

# Tab 8: Export
with tabs[7]:
    st.header("8. Export")
    schedule = st.session_state.get("amortization")
    if schedule is None or schedule.empty:
        schedule = amortization_schedule(
            principal=st.session_state["inputs"].get("loan_amount", 0.0),
            annual_rate_pct=st.session_state["inputs"].get("interest_rate", 0.0),
            months=int(st.session_state["inputs"].get("term_months", 60))
        )
    exp_choice = st.selectbox("Chọn loại xuất", ["Excel - Kế hoạch trả nợ", "DOCX - Báo cáo thẩm định", "PDF - Báo cáo thẩm định"])
    if st.button("Tạo & Tải"):
        inputs_copy = st.session_state["inputs"].copy()
        metrics_copy = compute_indicators(inputs_copy)
        if exp_choice.startswith("Excel"):
            excel = df_to_excel_bytes(schedule, info=inputs_copy, metrics=metrics_copy)
            st.download_button("Tải Excel", data=excel, file_name="ke_hoach_tra_no.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif exp_choice.startswith("DOCX"):
            if DocxWriter is None:
                st.error("python-docx chưa cài — không thể xuất DOCX.")
            else:
                docx_bytes = export_docx_bytes(inputs_copy, metrics_copy, schedule, analysis_text=st.session_state.get("analysis_inputs",""))
                st.download_button("Tải DOCX", data=docx_bytes, file_name="bao_cao_tham_dinh.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        elif exp_choice.startswith("PDF"):
            if SimpleDocTemplate is None:
                st.error("reportlab chưa cài — không thể xuất PDF.")
            else:
                chart = st.session_state.get("chart_png")
                pdf = create_pdf_report_bytes(inputs_copy, metrics_copy, schedule, chart, analysis_text=st.session_state.get("analysis_inputs",""))
                st.download_button("Tải PDF", data=pdf, file_name="bao_cao_tham_dinh.pdf", mime="application/pdf")

# Tab Debug
with tabs[8]:
    st.header("Debug")
    st.markdown("Dùng tab này để xem raw text và parsed fields (dễ debug khi deploy).")
    st.text_area("Raw extracted text", st.session_state.get("raw_text",""), height=300)
    st.write("Inputs state:", st.session_state["inputs"])
    st.write("Amortization head:")
    st.write(st.session_state.get("amortization").head() if not st.session_state.get("amortization").empty else "No schedule yet")
    st.write("Analysis (file):", st.session_state.get("analysis_file","")[:1000])
    st.write("Analysis (inputs):", st.session_state.get("analysis_inputs","")[:1000])
    st.write("Chat history len:", len(st.session_state.get("chat_history", [])))

st.markdown("---")
st.caption(".")
