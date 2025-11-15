import streamlit as st
import pandas as pd
import re
import io
import datetime
import unicodedata
from typing import Dict, Any

# -------- TRY IMPORT DOCX --------
try:
    from docx import Document
except:
    Document = None


# ============================================================
# 1) UTILITIES
# ============================================================

def normalize_text(t: str) -> str:
    """Chuẩn hóa unicode + bỏ khoảng trắng thừa"""
    t = unicodedata.normalize("NFC", t)
    t = t.replace("\r", "\n")
    while "  " in t:
        t = t.replace("  ", " ")
    return t


def extract_number(text: str) -> float:
    """Lấy số tiền từ chuỗi. Ví dụ: 5.000.000.000 => 5000000000"""
    if not text:
        return 0.0
    cleaned = text.replace(".", "").replace(",", "").replace(" ", "")
    m = re.search(r"(\d+)", cleaned)
    if not m:
        return 0.0
    return float(m.group(1))


def extract_percent(text: str) -> float:
    """Lấy % từ chuỗi 8.5% hoặc 8,5 %"""
    if not text:
        return 0.0
    t = text.replace(",", ".")
    m = re.search(r"(\d+(\.\d+)?)", t)
    return float(m.group(1)) if m else 0.0


def format_vnd(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


# ============================================================
# 2) LINH HOẠT EXTRACTOR
# ============================================================

def extract_fields(text: str) -> Dict[str, Any]:
    """Extractor linh hoạt, dùng fuzzy match theo từ khóa."""
    d = {
        "name": "",
        "cccd": "",
        "address": "",
        "phone": "",
        "purpose": "",
        "total_need": 0,
        "own_capital": 0,
        "loan_amount": 0,
        "interest_rate": 0.0,
        "term_months": 0,
        "total_income_month": 0,
        "monthly_expense": 0,
        "collateral_value": 0
    }

    t = normalize_text(text)
    lines = t.split("\n")

    # ---------- Name ----------
    for ln in lines:
        if "họ và tên" in ln.lower():
            m = re.search(r"Họ và tên[:\-– ]*(.*)", ln, re.IGNORECASE)
            if m:
                name = m.group(1)
                name = name.split("-")[0].strip()
                d["name"] = name
                break

    # ---------- CCCD ----------
    m = re.search(r"(CCCD|CMND|CMND\/CCCD)[^\d]*([\d]{9,12})", t, re.IGNORECASE)
    if m:
        d["cccd"] = m.group(2)

    # ---------- Phone ----------
    m = re.search(r"\b(0\d{9,10})\b", t)
    if m:
        d["phone"] = m.group(1)

    # ---------- Address ----------
    for ln in lines:
        if "địa chỉ" in ln.lower() or "nơi cư trú" in ln.lower():
            m = re.search(r"(Địa chỉ|Nơi cư trú)[:\-– ]*(.*)", ln, re.IGNORECASE)
            if m:
                d["address"] = m.group(2).strip()
                break

    # ---------- Purpose ----------
    for ln in lines:
        if "mục đích vay" in ln.lower():
            m = re.search(r"Mục đích vay[:\-– ]*(.*)", ln, re.IGNORECASE)
            if m:
                d["purpose"] = m.group(1).strip()
                break

    # ---------- Money Patterns ----------
    def find_money(keyword_list):
        for ln in lines:
            for kw in keyword_list:
                if kw in ln.lower():
                    m = re.search(r"([\d\.\, ]+)", ln)
                    if m:
                        return extract_number(m.group(1))
        return 0

    d["total_need"] = find_money(["tổng nhu cầu"])
    d["own_capital"] = find_money(["vốn đối ứng"])
    d["loan_amount"] = find_money(["vốn vay", "vay agribank"])

    # ---------- Interest Rate ----------
    for ln in lines:
        if "lãi suất" in ln.lower():
            m = re.search(r"([\d\.,]+)\s*%?", ln)
            if m:
                d["interest_rate"] = extract_percent(m.group(1))
                break

    # ---------- Term ----------
    m = re.search(r"(\d+)\s*tháng", t.lower())
    if m:
        d["term_months"] = int(m.group(1))
    else:
        m = re.search(r"(\d+)\s*năm", t.lower())
        if m:
            d["term_months"] = int(m.group(1)) * 12

    # ---------- Income ----------
    d["total_income_month"] = find_money(["thu nhập", "tổng thu nhập"])

    # ---------- Expense ----------
    d["monthly_expense"] = find_money(["chi phí hàng tháng", "tổng chi phí"])

    # ---------- Collateral ----------
    d["collateral_value"] = find_money(["giá trị", "tài sản"])

    return d


# ============================================================
# 3) TÍNH TOÁN TÀI CHÍNH
# ============================================================

def pmt(principal, rate_annual, months):
    r = rate_annual / 12 / 100
    if months <= 0:
        return 0
    if r == 0:
        return principal / months
    return principal * r / (1 - (1 + r)**(-months))


def amortization(principal, rate, months):
    df = []
    monthly = pmt(principal, rate, months)
    bal = principal
    for i in range(1, months + 1):
        interest = bal * rate / 12 / 100
        principal_pay = monthly - interest
        bal -= principal_pay
        if bal < 0:
            bal = 0
        df.append([i, monthly, principal_pay, interest, bal])
    return pd.DataFrame(df, columns=["Kỳ", "Gốc + Lãi", "Gốc", "Lãi", "Dư nợ"])


# ============================================================
# 4) STREAMLIT APP
# ============================================================

st.set_page_config(layout="wide", page_title="PASDV Analyzer")
st.title("📄 PASDV Analyzer – Extractor LINH HOẠT")

if "data" not in st.session_state:
    st.session_state.data = {}

uploaded = st.file_uploader("Tải file .docx của khách hàng", type=["docx"])

if uploaded and Document is None:
    st.error("python-docx chưa được cài. Kiểm tra requirements.txt")
    st.stop()

# -------- READ DOCX --------
if uploaded:
    doc = Document(uploaded)
    raw = "\n".join([p.text for p in doc.paragraphs])
    fields = extract_fields(raw)
    st.session_state.data = fields
    st.success("Đã đọc file thành công!")

# ============================================================
# 5) FORM NHẬP LIỆU
# ============================================================

d = st.session_state.get("data", {})

col1, col2 = st.columns(2)

with col1:
    d["name"] = st.text_input("Họ và tên", d.get("name", ""))
    d["cccd"] = st.text_input("CCCD", d.get("cccd", ""))
    d["phone"] = st.text_input("Điện thoại", d.get("phone", ""))

with col2:
    d["address"] = st.text_input("Địa chỉ", d.get("address", ""))
    d["purpose"] = st.text_input("Mục đích vay", d.get("purpose", ""))

d["total_need"] = st.number_input("Tổng nhu cầu vốn", value=float(d.get("total_need", 0)))
d["own_capital"] = st.number_input("Vốn đối ứng", value=float(d.get("own_capital", 0)))
d["loan_amount"] = st.number_input("Số tiền vay", value=float(d.get("loan_amount", 0)))
d["interest_rate"] = st.number_input("Lãi suất (%/năm)", value=float(d.get("interest_rate", 0)))
d["term_months"] = st.number_input("Thời hạn (tháng)", value=int(d.get("term_months", 0)))
d["total_income_month"] = st.number_input("Tổng thu nhập/tháng", value=float(d.get("total_income_month", 0)))
d["monthly_expense"] = st.number_input("Chi phí/tháng", value=float(d.get("monthly_expense", 0)))
d["collateral_value"] = st.number_input("Giá trị TSĐB", value=float(d.get("collateral_value", 0)))

st.session_state.data = d

# ============================================================
# 6) HIỂN THỊ KẾT QUẢ
# ============================================================

if st.button("Tính toán"):
    p = pmt(d["loan_amount"], d["interest_rate"], d["term_months"])
    st.subheader("📌 Kết quả tính toán")
    st.write("Thanh toán hàng tháng:", format_vnd(p))

    df = amortization(d["loan_amount"], d["interest_rate"], d["term_months"])
    st.dataframe(df.head())

    st.session_state.schedule = df

# ============================================================
# 7) DOWNLOAD
# ============================================================

if st.button("Tải Excel"):
    df = st.session_state.get("schedule")
    if df is None:
        st.warning("Chưa tính toán")
    else:
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        st.download_button("Download Excel", buf.getvalue(), "schedule.xlsx")
