# main.py
"""
PASDV Analyzer - Full rewritten Streamlit app
Features:
- Upload .docx (PASDV) and heuristic extraction
- Editable fields with +/- buttons and thousands separator "."
- Tabs: Identification, Finance, Collateral, Calculations, Charts, AI Analysis, Chat, Export
- Two AI analyses (from uploaded file, from adjusted inputs) using gemini-2.5-flash
- Chatbox with Gemini, clear chat
- Amortization schedule generation, Excel export
- DOCX/PDF export of report (DOCX via python-docx, PDF via reportlab)
- Safe imports and helpful error messages
Author: Generated for Huynh
"""
from __future__ import annotations
import io
import re
import math
import json
import datetime
from typing import Dict, Any, Optional, Tuple
import tempfile

import pandas as pd
import numpy as np
import streamlit as st

# safe imports
try:
    from docx import Document
except Exception:
    Document = None

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

try:
    import requests
except Exception:
    requests = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet
except Exception:
    # PDF export will be disabled if not installed
    SimpleDocTemplate = None

try:
    from docx import Document as DocxWriter
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
except Exception:
    DocxWriter = None

# ---------------------------
# CONFIG
# ---------------------------
GEMINI_API_URL = "https://api.example.com/gemini"  # replace with real endpoint if available
GEMINI_MODEL = "gemini-2.5-flash"

# ---------------------------
# UTILITIES: formatting & parsing
# ---------------------------
def format_thousands_dot(x: Optional[float]) -> str:
    """Format integer-like numbers with '.' as thousand separator, no decimals."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    try:
        # round to 0 decimals for display of monetary amounts
        val = float(x)
        s = f"{val:,.0f}"
        return s.replace(",", ".")
    except Exception:
        return str(x)

def format_number_readable(x: Optional[float], decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    try:
        val = float(x)
        if decimals == 0:
            return format_thousands_dot(val)
        s = f"{val:,.{decimals}f}"
        # python uses comma as thousands sep; replace appropriately
        s = s.replace(",", "_").replace(".", ",").replace("_", ".")
        return s
    except Exception:
        return str(x)

def vnd_to_float(s: Optional[str]) -> float:
    """Parse VND text like '5.000.000.000 đồng' or '5,000,000,000' or '5000000' -> float"""
    if s is None:
        return 0.0
    s = str(s).strip()
    # remove words
    s = s.replace("đồng", "").replace("VND", "").replace("vnđ", "").replace("₫", "")
    s = s.replace(" ", "")
    # If both '.' and ',' present, assume '.' is thousands and ',' is decimal OR vice versa.
    # Heuristic: if there are '.' and groups of 3 between them -> remove dots.
    if "." in s and "," in s:
        # common Vietnamese format: 1.234.567,89
        s = s.replace(".", "").replace(",", ".")
    else:
        # remove thousands separator dots or commas, keep dot as decimal if it's the only one and there are decimals
        if s.count(".") > 1:
            s = s.replace(".", "")
        if s.count(",") > 1:
            s = s.replace(",", "")
        s = s.replace(",", ".")
        s = s.replace(".", "") if s.isdigit() else s
    # final sanitize
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

# ---------------------------
# DOCX extraction heuristics
# ---------------------------
def extract_text_docx_bytes(file_bytes: bytes) -> str:
    if Document is None:
        return ""
    bio = io.BytesIO(file_bytes)
    doc = Document(bio)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(paragraphs)

def extract_fields_from_text(text: str) -> Dict[str, Any]:
    """
    Heuristic extraction tuned to the PASDV.docx sample.
    Returns dict with keys used by app.
    """
    out: Dict[str, Any] = {
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
        "collateral_value": 0.0,
    }
    if not text:
        return out
    # Normalize spaces
    t = text.replace("\r", "\n")
    # name: look for 'Họ và tên: ...' or numbered list '1. Họ và tên: ...'
    m = re.search(r"Họ\s+và\s+tên\s*[:\-–]?\s*([A-Za-zÀ-ỹ\s]+(?:[A-Za-zÀ-ỹ\s]+)?)", t, flags=re.IGNORECASE)
    if m:
        out["name"] = m.group(1).strip()
    # cccd: look for 9-12 digits after CMND/CCCD
    m = re.search(r"(?:CMND|CCCD|CMND\/CCCD).*?[:\-–]?\s*([0-9]{9,12})", t, flags=re.IGNORECASE)
    if m:
        out["cccd"] = m.group(1).strip()
    # phone
    m = re.search(r"Số\s*điện\s*thoại\s*[:\-–]?\s*(0\d{8,10})", t, flags=re.IGNORECASE)
    if m:
        out["phone"] = m.group(1).strip()
    else:
        m = re.search(r"\b(0\d{8,10})\b", t)
        if m:
            out["phone"] = m.group(1)
    # email
    m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", t)
    if m:
        out["email"] = m.group(0)
    # address
    m = re.search(r"Nơi\s*cư\s*trú\s*[:\-–]?\s*([^\n]+)", t, flags=re.IGNORECASE)
    if m:
        out["address"] = m.group(1).strip()
    # purpose
    m = re.search(r"Mục\s*đích\s*vay\s*[:\-–]?\s*([^\n]+)", t, flags=re.IGNORECASE)
    if m:
        out["purpose"] = m.group(1).strip()
    # total need
    m = re.search(r"Tổng\s*nhu\s*cầu\s*vốn\s*[:\-–]?\s*([\d\.,\s]+)\s*đồng?", t, flags=re.IGNORECASE)
    if m:
        out["total_need"] = vnd_to_float(m.group(1))
    # own capital
    m = re.search(r"Vốn\s*đối\s*ứng.*?([\d\.,\s]+)\s*đồng?", t, flags=re.IGNORECASE)
    if m:
        out["own_capital"] = vnd_to_float(m.group(1))
    # loan amount (vốn vay Agribank số tiền)
    m = re.search(r"Vốn\s*vay.*?[\:–\-]?\s*([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
    if m:
        out["loan_amount"] = vnd_to_float(m.group(1))
    # interest
    m = re.search(r"Lãi\s*suất\s*[:\-–]?\s*([\d\.,]+)\s*%/?năm?", t, flags=re.IGNORECASE)
    if m:
        out["interest_rate"] = percent_to_float(m.group(1))
    else:
        # fallback: find pattern like '8,5%/năm' anywhere
        m = re.search(r"(\d+[.,]?\d*)\s*%/năm", t)
        if m:
            out["interest_rate"] = percent_to_float(m.group(1))
    # term months: look for '60 tháng' or '(5 năm)'
    m = re.search(r"Thời\s*hạn\s*vay\s*[:\-–]?\s*(\d+)\s*tháng", t, flags=re.IGNORECASE)
    if m:
        out["term_months"] = int(m.group(1))
    else:
        m = re.search(r"Thời\s*hạn\s*vay.*?(\d+)\s*năm", t, flags=re.IGNORECASE)
        if m:
            out["term_months"] = int(m.group(1)) * 12
    # project income from text: "30.000.000 đồng/tháng"
    m = re.search(r"([\d\.,\s]+)\s*đồng\s*/\s*tháng", t)
    if m:
        # choose the first reasonable monthly amount as project income maybe
        val = vnd_to_float(m.group(1))
        # if less than 1e7 maybe it's monthly expense, so be cautious; we will later try to detect total income
        out["project_income_month"] = val
    # salary income detection lines like 'Thu nhập từ lương: 70.000.000 đồng/tháng'
    m = re.search(r"Thu\s*nhập\s*(?:từ\s*lương)?\s*[:\-–]?\s*([\d\.,\s]+)\s*đồng\s*/\s*tháng", t, flags=re.IGNORECASE)
    if m:
        out["salary_income_month"] = vnd_to_float(m.group(1))
    # total income
    m = re.search(r"Tổng\s*thu\s*nhập.*?([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
    if m:
        out["total_income_month"] = vnd_to_float(m.group(1))
    else:
        # fallback: sum salary + project
        out["total_income_month"] = out.get("salary_income_month", 0.0) + out.get("project_income_month", 0.0)
    # monthly expense
    m = re.search(r"Tổng\s*chi\s*phí\s*hàng\s*tháng\s*[:\-–]?\s*([\d\.,\s]+)\s*(?:đồng)?", t, flags=re.IGNORECASE)
    if m:
        out["monthly_expense"] = vnd_to_float(m.group(1))
    # collateral value: 'Giá trị: 6.000.000.000 đồng' or 'Giá trị nhà dự kiến mua: 6.000.000.000 đồng'
    m = re.search(r"Giá\s*trị(?:\s*nhà.*|)\s*(?:dự\s*kiến\s*mua\s*:|:)?\s*([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
    if m:
        out["collateral_value"] = vnd_to_float(m.group(1))
    # If collateral not found, look for 'Giá trị: 6.000.000.000 đồng' near 'Tài sản' words
    if out["collateral_value"] == 0:
        m = re.search(r"Tài\s*sản[^\n]{0,80}Giá\s*trị\s*[:\-–]?\s*([\d\.,\s]+)\s*đồng", t, flags=re.IGNORECASE)
        if m:
            out["collateral_value"] = vnd_to_float(m.group(1))
    # final adjustments: ensure numeric fields non-negative
    for k in ["total_need", "own_capital", "loan_amount", "interest_rate", "term_months",
              "project_income_month", "salary_income_month", "total_income_month", "monthly_expense",
              "collateral_value"]:
        if k in out and out[k] is None:
            out[k] = 0.0
    return out

# ---------------------------
# FINANCIAL calculations
# ---------------------------
def annuity_monthly_payment(principal: float, annual_rate_pct: float, months: int) -> float:
    """Compute annuity (fixed payment) monthly."""
    try:
        principal = float(principal)
        r = float(annual_rate_pct) / 100.0 / 12.0
        n = int(months)
        if n <= 0:
            return 0.0
        if r == 0:
            return principal / n
        # standard annuity formula:
        payment = principal * r / (1 - (1 + r) ** (-n))
        return float(payment)
    except Exception:
        return 0.0

def amortization_schedule(principal: float, annual_rate_pct: float, months: int, start_date: Optional[datetime.date] = None) -> pd.DataFrame:
    if months <= 0 or principal <= 0:
        return pd.DataFrame(columns=["Month", "Date", "Payment", "Principal", "Interest", "Remaining"])
    if start_date is None:
        start_date = datetime.date.today()
    r = float(annual_rate_pct) / 100.0 / 12.0
    payment = annuity_monthly_payment(principal, annual_rate_pct, months)
    schedule = []
    balance = float(principal)
    for i in range(1, months + 1):
        interest = balance * r
        principal_paid = payment - interest
        if principal_paid > balance:
            principal_paid = balance
            payment = principal_paid + interest
        balance = max(0.0, balance - principal_paid)
        pay_date = start_date + pd.DateOffset(months=i)
        schedule.append({
            "Month": i,
            "Date": pay_date.strftime("%Y-%m-%d"),
            "Payment": round(payment, 0),
            "Principal": round(principal_paid, 0),
            "Interest": round(interest, 0),
            "Remaining": round(balance, 0)
        })
    return pd.DataFrame(schedule)

def compute_indicators_from_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    loan = float(inputs.get("loan_amount", 0.0))
    rate = float(inputs.get("interest_rate", 0.0))
    term = int(inputs.get("term_months", 0))
    income = float(inputs.get("total_income_month", 0.0))
    expense = float(inputs.get("monthly_expense", 0.0))
    collateral = float(inputs.get("collateral_value", 0.0))
    pmt = annuity_monthly_payment(loan, rate, term)
    total_pay = pmt * (term or 1)
    dsr = pmt / income if income > 0 else float("nan")
    ltv = loan / collateral if collateral > 0 else float("nan")
    net_cashflow = income - expense - pmt
    # other CADAP-ish metrics:
    e_over_c = inputs.get("own_capital", 0.0) / (inputs.get("total_need", 1.0)) if inputs.get("total_need", 0.0) > 0 else float("nan")
    debt_over_income = (inputs.get("loan_amount", 0.0) + inputs.get("tong_no_hien_tai", 0.0)) / max(1e-9, income * 12.0)
    cfr = (income - pmt) / income if income > 0 else float("nan")
    coverage = collateral / max(1e-9, loan) if loan > 0 else float("nan")
    # aggregate score (simple demo)
    score = 0.0
    try:
        if not math.isnan(dsr):
            score += max(0.0, 1.0 - min(1.0, dsr)) * 0.25
        if not math.isnan(ltv):
            score += max(0.0, 1.0 - min(1.0, ltv)) * 0.25
        if not math.isnan(e_over_c):
            score += min(1.0, e_over_c / 0.3) * 0.2
        if not math.isnan(cfr):
            score += max(0.0, min(1.0, cfr)) * 0.2
        if not math.isnan(coverage):
            score += min(1.0, coverage / 1.5) * 0.1
    except Exception:
        pass
    return {
        "PMT_month": pmt,
        "Total_payment": total_pay,
        "DSR": dsr,
        "LTV": ltv,
        "Net_cashflow": net_cashflow,
        "E_over_C": e_over_c,
        "Debt_over_Income": debt_over_income,
        "CFR": cfr,
        "Coverage": coverage,
        "Score": round(score, 3)
    }

# ---------------------------
# AI / Gemini wrapper
# ---------------------------
def call_gemini_api(prompt: str, api_key: str, model: str = GEMINI_MODEL, max_tokens: int = 512) -> str:
    """Simple wrapper to call Gemini-like REST endpoint. The payload & headers might need adjustment to real API."""
    if requests is None:
        return "Requests library not available."
    if not api_key:
        return "No API key configured."
    payload = {
        "model": model,
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
            try:
                j = r.json()
                # attempt common fields
                for k in ("text", "content", "output", "response"):
                    if k in j:
                        return j[k] or str(j)
                if "choices" in j and isinstance(j["choices"], list) and len(j["choices"]) > 0:
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

# ---------------------------
# EXPORT: Excel / PDF / DOCX
# ---------------------------
def df_to_excel_bytes(df: pd.DataFrame, info: Dict[str, Any] = None, metrics: Dict[str, Any] = None) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Amortization", index=False)
        if info is not None:
            pd.DataFrame([info]).to_excel(writer, sheet_name="Info", index=False)
        if metrics is not None:
            pd.DataFrame([metrics]).to_excel(writer, sheet_name="Metrics", index=False)
    buf.seek(0)
    return buf.getvalue()

def create_pdf_report_bytes(inputs: Dict[str, Any], metrics: Dict[str, Any], schedule_df: pd.DataFrame, chart_bytes: Optional[bytes], analysis_text: str = "") -> bytes:
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
        if isinstance(v, float):
            elems.append(Paragraph(f"{k}: {format_number_readable(v)}", styles["Normal"]))
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

def export_docx_bytes(inputs: Dict[str, Any], metrics: Dict[str, Any], schedule_df: pd.DataFrame, analysis_text: str = "") -> bytes:
    if DocxWriter is None:
        return b""
    doc = DocxWriter()
    doc.add_heading("BÁO CÁO THẨM ĐỊNH PHƯƠNG ÁN SỬ DỤNG VỐN", level=1)
    doc.add_paragraph(f"Khách hàng: {inputs.get('name','')}")
    doc.add_paragraph(f"Mục đích: {inputs.get('purpose','')}")
    doc.add_paragraph("Chỉ tiêu:")
    for k, v in metrics.items():
        doc.add_paragraph(f"- {k}: {format_number_readable(v)}")
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
    for i, row in schedule_df.head(5).iterrows():
        r = table.add_row().cells
        r[0].text = str(row["Month"])
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

# ---------------------------
# STREAMLIT UI
# ---------------------------
st.set_page_config(page_title="PASDV - Analyzer", layout="wide")

st.title("PASDV Analyzer — Phân tích Phương Án Sử Dụng Vốn")
st.markdown("Giao diện: phân tab — nhập/ chỉnh sửa — tính toán — AI Gemini — export")

# Sidebar: API key + options (left)
with st.sidebar:
    st.header("Cấu hình")
    api_key = st.text_input("API Key Gemini (gemini-2.5-flash)", type="password")
    st.write("Bạn có thể nhập API key ở đây để bật phân tích AI và chatbox.")
    st.markdown("---")
    st.write("Xuất báo cáo:")
    default_export = st.selectbox("Định dạng mặc định khi tải", ["PDF", "DOCX", "Excel"], index=0)
    st.markdown("---")
    st.write("Ghi chú:")
    st.caption("Format số: hàng nghìn phân cách bằng dấu '.' (ví dụ: 1.000.000)")

# Initialize session state containers
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
        "tong_no_hien_tai": 0.0,
    }
if "raw_upload_text" not in st.session_state:
    st.session_state["raw_upload_text"] = ""
if "amortization" not in st.session_state:
    st.session_state["amortization"] = pd.DataFrame()
if "analysis_file" not in st.session_state:
    st.session_state["analysis_file"] = ""
if "analysis_inputs" not in st.session_state:
    st.session_state["analysis_inputs"] = ""
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Upload area (left column)
upload_col, tabs_col = st.columns([1, 3])
with upload_col:
    st.header("Upload hồ sơ (.docx)")
    uploaded = st.file_uploader("Upload file PASDV (.docx) để tự động trích xuất", type=["docx"])
    if uploaded is not None:
        try:
            raw_text = extract_text_docx_bytes(uploaded.read())
            st.session_state["raw_upload_text"] = raw_text
            st.success("Đã đọc file. Xin kiểm tra và chỉnh sửa bên tab '1. Identification'.")
            # parse heuristics
            parsed = extract_fields_from_text(raw_text)
            # merge parsed into inputs but do not overwrite non-empty manual edits
            for k, v in parsed.items():
                if v is None:
                    continue
                # map parsed keys to session inputs
                if k == "name" and parsed["name"]:
                    st.session_state["inputs"]["name"] = parsed["name"]
                if k == "cccd" and parsed["cccd"]:
                    st.session_state["inputs"]["cccd"] = parsed["cccd"]
                if k == "address" and parsed["address"]:
                    st.session_state["inputs"]["address"] = parsed["address"]
                if k == "phone" and parsed["phone"]:
                    st.session_state["inputs"]["phone"] = parsed["phone"]
                if k == "email" and parsed["email"]:
                    st.session_state["inputs"]["email"] = parsed["email"]
                if k == "purpose" and parsed["purpose"]:
                    st.session_state["inputs"]["purpose"] = parsed["purpose"]
                if k == "total_need" and parsed["total_need"]:
                    st.session_state["inputs"]["total_need"] = parsed["total_need"]
                if k == "own_capital" and parsed["own_capital"]:
                    st.session_state["inputs"]["own_capital"] = parsed["own_capital"]
                if k == "loan_amount" and parsed["loan_amount"]:
                    st.session_state["inputs"]["loan_amount"] = parsed["loan_amount"]
                if k == "interest_rate" and parsed["interest_rate"]:
                    st.session_state["inputs"]["interest_rate"] = parsed["interest_rate"]
                if k == "term_months" and parsed["term_months"]:
                    st.session_state["inputs"]["term_months"] = parsed["term_months"]
                if k == "project_income_month" and parsed["project_income_month"]:
                    st.session_state["inputs"]["project_income_month"] = parsed["project_income_month"]
                if k == "salary_income_month" and parsed["salary_income_month"]:
                    st.session_state["inputs"]["salary_income_month"] = parsed["salary_income_month"]
                if k == "total_income_month" and parsed["total_income_month"]:
                    st.session_state["inputs"]["total_income_month"] = parsed["total_income_month"]
                if k == "monthly_expense" and parsed["monthly_expense"]:
                    st.session_state["inputs"]["monthly_expense"] = parsed["monthly_expense"]
                if k == "collateral_value" and parsed["collateral_value"]:
                    st.session_state["inputs"]["collateral_value"] = parsed["collateral_value"]
            # ensure total_income_month sensible
            if st.session_state["inputs"]["total_income_month"] == 0:
                st.session_state["inputs"]["total_income_month"] = st.session_state["inputs"].get("salary_income_month", 0.0) + st.session_state["inputs"].get("project_income_month", 0.0)
        except Exception as e:
            st.error(f"Lỗi khi đọc file: {e}")
    st.markdown("---")
    if st.button("Reset tất cả"):
        for k in st.session_state["inputs"].keys():
            if isinstance(st.session_state["inputs"][k], (int, float)):
                st.session_state["inputs"][k] = 0.0
            else:
                st.session_state["inputs"][k] = ""
        st.session_state["raw_upload_text"] = ""
        st.session_state["amortization"] = pd.DataFrame()
        st.experimental_rerun()
    st.markdown("### Preview trích xuất")
    st.text_area("Raw extracted text (preview)", st.session_state["raw_upload_text"], height=250)

# Tabs for data and actions
tabs = tabs_col.tabs([
    "1. Identification",
    "2. Finance",
    "3. Collateral",
    "4. Calculations",
    "5. Charts",
    "6. AI Analysis",
    "7. Chatbox",
    "8. Export"
])

# ---------------------------
# Tab 1: Identification
# ---------------------------
with tabs[0]:
    st.header("1. Identification")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Họ và tên khách hàng", key="name_input", value=st.session_state["inputs"]["name"], on_change=lambda: st.session_state["inputs"].update({"name": st.session_state.get("name_input","")}))
        st.text_input("CCCD/CMND", key="cccd_input", value=st.session_state["inputs"].get("cccd",""), on_change=lambda: st.session_state["inputs"].update({"cccd": st.session_state.get("cccd_input","")}))
        st.text_input("Nơi cư trú", key="address_input", value=st.session_state["inputs"]["address"], on_change=lambda: st.session_state["inputs"].update({"address": st.session_state.get("address_input","")}))
    with col2:
        st.text_input("Số điện thoại", key="phone_input", value=st.session_state["inputs"].get("phone",""), on_change=lambda: st.session_state["inputs"].update({"phone": st.session_state.get("phone_input","")}))
        st.text_input("Email", key="email_input", value=st.session_state["inputs"].get("email",""), on_change=lambda: st.session_state["inputs"].update({"email": st.session_state.get("email_input","")}))
        st.text_input("Mục đích vay", key="purpose_input", value=st.session_state["inputs"].get("purpose",""), on_change=lambda: st.session_state["inputs"].update({"purpose": st.session_state.get("purpose_input","")}))

# helper to show numeric input with +/- buttons and dot formatting
def vn_money_widget(label: str, session_key: str, step: float = 1000000.0):
    col_a, col_b, col_c = st.columns([3, 1, 1])
    current = st.session_state["inputs"].get(session_key, 0.0)
    display = format_thousands_dot(current)
    with col_a:
        raw = st.text_input(label, value=display, key=f"txt_{session_key}")
        # parse when changed
        parsed = vnd_to_float(raw)
        st.session_state["inputs"][session_key] = parsed
    with col_b:
        if st.button("+", key=f"plus_{session_key}"):
            st.session_state["inputs"][session_key] = st.session_state["inputs"].get(session_key, 0.0) + step
    with col_c:
        if st.button("-", key=f"minus_{session_key}"):
            st.session_state["inputs"][session_key] = max(0.0, st.session_state["inputs"].get(session_key, 0.0) - step)

def percent_widget(label: str, session_key: str):
    col_a, col_b = st.columns([3, 1])
    current = st.session_state["inputs"].get(session_key, 0.0)
    display = f"{current:.2f}".replace(".", ",")
    with col_a:
        raw = st.text_input(label, value=display, key=f"pct_{session_key}")
        st.session_state["inputs"][session_key] = percent_to_float(raw)
    with col_b:
        st.write("")  # spacer

# ---------------------------
# Tab 2: Finance
# ---------------------------
with tabs[1]:
    st.header("2. Finance / Loan")
    vn_money_widget("Tổng nhu cầu vốn (VND)", "total_need", step=100_000_000)
    vn_money_widget("Vốn đối ứng (VND)", "own_capital", step=50_000_000)
    vn_money_widget("Số tiền vay (VND)", "loan_amount", step=100_000_000)
    percent_widget("Lãi suất (%/năm)", "interest_rate")
    col_a, col_b = st.columns(2)
    with col_a:
        st.number_input("Thời hạn vay (tháng)", min_value=1, max_value=600, value=int(st.session_state["inputs"].get("term_months", 60)), key="term_months_input", on_change=lambda: st.session_state["inputs"].update({"term_months": int(st.session_state.get("term_months_input",60))}))
    with col_b:
        # display computed ratio total_need vs (own + loan)
        tn = st.session_state["inputs"].get("total_need", 0.0)
        own = st.session_state["inputs"].get("own_capital", 0.0)
        loan = st.session_state["inputs"].get("loan_amount", 0.0)
        st.write("Tổng nhu cầu (hiện):", format_thousands_dot(tn))
        st.write("Vốn đối ứng + Vay:", format_thousands_dot(own + loan))
        if tn != 0 and abs((own + loan) - tn) > 1.0:
            st.warning("Lưu ý: Tổng vốn đối ứng + Số tiền vay khác Tổng nhu cầu vốn. Hãy kiểm tra/ chỉnh sửa nếu cần.")

# ---------------------------
# Tab 3: Collateral
# ---------------------------
with tabs[2]:
    st.header("3. Collateral / Tài sản bảo đảm")
    vn_money_widget("Giá trị TSĐB (VND)", "collateral_value", step=100_000_000)
    st.text_input("Địa chỉ TSĐB (nếu có)", key="collateral_address", value=st.session_state["inputs"].get("collateral_address",""), on_change=lambda: st.session_state["inputs"].update({"collateral_address": st.session_state.get("collateral_address","")}))
    st.text_input("Giấy tờ pháp lý", key="collateral_docs", value=st.session_state["inputs"].get("collateral_docs",""), on_change=lambda: st.session_state["inputs"].update({"collateral_docs": st.session_state.get("collateral_docs","")}))

# ---------------------------
# Tab 4: Calculations
# ---------------------------
with tabs[3]:
    st.header("4. Calculations & Indicators")
    # ensure derived total_income_month computed
    if st.session_state["inputs"].get("total_income_month", 0.0) == 0:
        st.session_state["inputs"]["total_income_month"] = st.session_state["inputs"].get("salary_income_month", 0.0) + st.session_state["inputs"].get("project_income_month", 0.0)
    st.write("Thu nhập tháng (Tổng):", format_thousands_dot(st.session_state["inputs"].get("total_income_month", 0.0)))
    metrics = compute_indicators_from_inputs({
        "loan_amount": st.session_state["inputs"].get("loan_amount", 0.0),
        "interest_rate": st.session_state["inputs"].get("interest_rate", 0.0),
        "term_months": st.session_state["inputs"].get("term_months", 60),
        "total_income_month": st.session_state["inputs"].get("total_income_month", 0.0),
        "monthly_expense": st.session_state["inputs"].get("monthly_expense", 0.0),
        "collateral_value": st.session_state["inputs"].get("collateral_value", 0.0),
        "own_capital": st.session_state["inputs"].get("own_capital", 0.0),
        "total_need": st.session_state["inputs"].get("total_need", 0.0),
        "tong_no_hien_tai": st.session_state["inputs"].get("tong_no_hien_tai", 0.0)
    })
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Thanh toán hàng tháng (PMT)", format_thousands_dot(metrics["PMT_month"]))
        st.metric("Tổng trả (ước tính)", format_thousands_dot(metrics["Total_payment"]))
    with c2:
        st.metric("DSR (<= 80%)", f"{metrics['DSR']*100:.2f}%" if not math.isnan(metrics["DSR"]) else "n/a")
        st.metric("LTV (<= 80%)", f"{metrics['LTV']*100:.2f}%" if not math.isnan(metrics["LTV"]) else "n/a")
    with c3:
        st.metric("CFR (cash flow ratio)", f"{metrics['CFR']*100:.2f}%" if not math.isnan(metrics["CFR"]) else "n/a")
        st.metric("Coverage", f"{metrics['Coverage']:.2f}" if not math.isnan(metrics["Coverage"]) else "n/a")
    st.markdown("**Ghi chú:** Số liệu tính toán theo phương pháp annuity (trả đều).")

    if st.button("Tạo lịch trả nợ (amortization)"):
        schedule = amortization_schedule(
            principal=st.session_state["inputs"].get("loan_amount", 0.0),
            annual_rate_pct=st.session_state["inputs"].get("interest_rate", 0.0),
            months=int(st.session_state["inputs"].get("term_months", 60)),
            start_date=datetime.date.today()
        )
        st.session_state["amortization"] = schedule
        st.success("Đã tạo lịch trả nợ. Sang tab 'Charts' hoặc 'Export' để tải.")

# ---------------------------
# Tab 5: Charts
# ---------------------------
with tabs[4]:
    st.header("5. Charts")
    schedule = st.session_state.get("amortization")
    if schedule is None or schedule.empty:
        schedule = amortization_schedule(
            principal=st.session_state["inputs"].get("loan_amount", 0.0),
            annual_rate_pct=st.session_state["inputs"].get("interest_rate", 0.0),
            months=int(st.session_state["inputs"].get("term_months", 60)),
            start_date=datetime.date.today()
        )
    if plt is None:
        st.warning("Matplotlib chưa cài: không thể vẽ biểu đồ.")
    else:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(schedule["Month"], schedule["Payment"], label="Payment")
        ax.plot(schedule["Month"], schedule["Principal"], label="Principal")
        ax.plot(schedule["Month"], schedule["Interest"], label="Interest")
        ax.set_xlabel("Month")
        ax.set_ylabel("VND")
        ax.legend()
        st.pyplot(fig)
        # capture chart bytes for PDF
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        chart_png = buf.getvalue()

    st.markdown("Biểu đồ nghĩa vụ trả nợ - thanh toán, tiền gốc, tiền lãi theo kỳ.")

# ---------------------------
# Tab 6: AI Analysis (two parts)
# ---------------------------
with tabs[5]:
    st.header("6. Phân tích AI (Gemini)")
    colA, colB = st.columns(2)
    with colA:
        st.subheader("A. Phân tích dựa trên File Upload")
        st.markdown("Nguồn dữ liệu: File .docx upload (raw)")
        if st.button("Phân tích từ File Upload"):
            if not st.session_state.get("raw_upload_text"):
                st.warning("Chưa upload file hoặc file không có nội dung.")
            else:
                prompt = (
                    "Bạn là chuyên viên thẩm định tín dụng.\n"
                    "Hãy phân tích ngắn gọn (tối đa 300 từ) phương án vay dựa trên dữ liệu gốc dưới đây.\n"
                    "Trả lời gồm: tóm tắt; rủi ro chính; khả năng trả nợ; đề xuất (cho vay/cho vay có điều kiện/không cho vay).\n\n"
                    f"--- Dữ liệu gốc (file upload):\n{st.session_state.get('raw_upload_text')[:6000]}"
                )
                with st.spinner("Gọi Gemini..."):
                    out = call_gemini_api(prompt, api_key or "", model=GEMINI_MODEL, max_tokens=600)
                    st.session_state["analysis_file"] = out
                    st.success("Hoàn tất phân tích từ file.")
        if st.session_state.get("analysis_file"):
            st.text_area("Kết quả phân tích (File Upload)", st.session_state.get("analysis_file"), height=250)

    with colB:
        st.subheader("B. Phân tích dựa trên dữ liệu đã chỉnh sửa")
        st.markdown("Nguồn dữ liệu: Dữ liệu nhập/chỉnh sửa (GUI)")
        if st.button("Phân tích từ dữ liệu đã chỉnh sửa"):
            inputs_snapshot = st.session_state["inputs"].copy()
            metrics_snapshot = compute_indicators_from_inputs({
                "loan_amount": inputs_snapshot.get("loan_amount", 0.0),
                "interest_rate": inputs_snapshot.get("interest_rate", 0.0),
                "term_months": inputs_snapshot.get("term_months", 60),
                "total_income_month": inputs_snapshot.get("total_income_month", 0.0),
                "monthly_expense": inputs_snapshot.get("monthly_expense", 0.0),
                "collateral_value": inputs_snapshot.get("collateral_value", 0.0),
                "own_capital": inputs_snapshot.get("own_capital", 0.0),
                "total_need": inputs_snapshot.get("total_need", 0.0),
                "tong_no_hien_tai": inputs_snapshot.get("tong_no_hien_tai", 0.0)
            })
            prompt2 = (
                "Bạn là chuyên viên thẩm định tín dụng.\n"
                "Phân tích hồ sơ sau dựa trên các chỉ số đã tính và dữ liệu chỉnh sửa (nguồn: giao diện người dùng).\n"
                "Trả lời gồm: tóm tắt số liệu quan trọng; rủi ro; đề xuất (ngắn gọn <= 300 từ).\n\n"
                f"--- Dữ liệu nhập:\n{json.dumps(inputs_snapshot, ensure_ascii=False)}\n\n"
                f"--- Chỉ số tính toán:\n{json.dumps(metrics_snapshot, ensure_ascii=False)}"
            )
            with st.spinner("Gọi Gemini..."):
                out2 = call_gemini_api(prompt2, api_key or "", model=GEMINI_MODEL, max_tokens=600)
                st.session_state["analysis_inputs"] = out2
                st.success("Hoàn tất phân tích từ dữ liệu đã chỉnh sửa.")
        if st.session_state.get("analysis_inputs"):
            st.text_area("Kết quả phân tích (Dữ liệu đã chỉnh sửa)", st.session_state.get("analysis_inputs"), height=250)

# ---------------------------
# Tab 7: Chatbox Gemini
# ---------------------------
with tabs[6]:
    st.header("7. Chatbox Gemini")
    st.markdown("Chat trực tiếp với Gemini (API key required). Nút 'Clear' để xóa lịch sử chat.")
    col1, col2 = st.columns([4,1])
    with col1:
        question = st.text_input("Nhập câu hỏi cho AI về hồ sơ này...")
    with col2:
        if st.button("Gửi"):
            if not question:
                st.warning("Nhập câu hỏi trước.")
            else:
                st.session_state["chat_history"].append({"role": "user", "text": question})
                # prepare context: include either raw file text or inputs summary
                context = st.session_state.get("raw_upload_text") or json.dumps(st.session_state["inputs"], ensure_ascii=False)
                prompt_chat = f"Người dùng hỏi: {question}\nContext: {context[:4000]}"
                with st.spinner("Gọi Gemini..."):
                    resp = call_gemini_api(prompt_chat, api_key or "", model=GEMINI_MODEL, max_tokens=400)
                    st.session_state["chat_history"].append({"role": "assistant", "text": resp})
    col3, col4 = st.columns([1,1])
    with col3:
        if st.button("Xóa hội thoại"):
            st.session_state["chat_history"] = []
            st.success("Đã xóa.")
    # display chat
    for msg in st.session_state["chat_history"]:
        if msg["role"] == "user":
            st.markdown(f"**Bạn:** {msg['text']}")
        else:
            st.markdown(f"**Gemini:** {msg['text']}")

# ---------------------------
# Tab 8: Export
# ---------------------------
with tabs[7]:
    st.header("8. Export")
    # ensure amortization built
    schedule = st.session_state.get("amortization")
    if schedule is None or schedule.empty:
        schedule = amortization_schedule(
            principal=st.session_state["inputs"].get("loan_amount", 0.0),
            annual_rate_pct=st.session_state["inputs"].get("interest_rate", 0.0),
            months=int(st.session_state["inputs"].get("term_months", 60)),
            start_date=datetime.date.today()
        )
    st.subheader("Xuất bảng kê / báo cáo")
    exp_choice = st.selectbox("Chọn xuất", ["Excel - Kế hoạch trả nợ", "DOCX - Báo cáo thẩm định", "PDF - Báo cáo thẩm định"])
    if st.button("Tạo & Tải"):
        inputs_copy = st.session_state["inputs"].copy()
        metrics_copy = compute_indicators_from_inputs({
            "loan_amount": inputs_copy.get("loan_amount", 0.0),
            "interest_rate": inputs_copy.get("interest_rate", 0.0),
            "term_months": inputs_copy.get("term_months", 60),
            "total_income_month": inputs_copy.get("total_income_month", 0.0),
            "monthly_expense": inputs_copy.get("monthly_expense", 0.0),
            "collateral_value": inputs_copy.get("collateral_value", 0.0),
            "own_capital": inputs_copy.get("own_capital", 0.0),
            "total_need": inputs_copy.get("total_need", 0.0),
            "tong_no_hien_tai": inputs_copy.get("tong_no_hien_tai", 0.0)
        })
        if exp_choice.startswith("Excel"):
            excel_bytes = df_to_excel_bytes(schedule, info=inputs_copy, metrics=metrics_copy)
            st.download_button("Tải Excel lịch trả nợ", data=excel_bytes, file_name="ke_hoach_tra_no.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif exp_choice.startswith("DOCX"):
            if DocxWriter is None:
                st.error("python-docx chưa cài, không thể xuất DOCX.")
            else:
                docx_bytes = export_docx_bytes(inputs_copy, metrics_copy, schedule, analysis_text=st.session_state.get("analysis_inputs",""))
                st.download_button("Tải DOCX báo cáo", data=docx_bytes, file_name="bao_cao_tham_dinh.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        elif exp_choice.startswith("PDF"):
            if SimpleDocTemplate is None:
                st.error("reportlab chưa cài, không thể xuất PDF.")
            else:
                # build chart image
                chart_png_bytes = None
                if plt is not None:
                    fig, ax = plt.subplots(figsize=(8,3))
                    ax.plot(schedule["Month"], schedule["Payment"])
                    ax.set_title("Payment over time")
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", bbox_inches="tight")
                    chart_png_bytes = buf.getvalue()
                pdf_bytes = create_pdf_report_bytes(inputs_copy, metrics_copy, schedule, chart_png_bytes, analysis_text=st.session_state.get("analysis_inputs",""))
                st.download_button("Tải PDF báo cáo", data=pdf_bytes, file_name="bao_cao_tham_dinh.pdf", mime="application/pdf")

st.markdown("---")
st.caption("Ứng dụng PASDV — Muội viết lại bản full code. Muội có thể tách thành modules, push lên GitHub và thêm CI/CD nếu Huynh muốn.")
