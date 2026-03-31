
import io
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st
import yfinance as yf
from PIL import Image, ImageOps

try:
    from rapidocr_onnxruntime import RapidOCR
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


st.set_page_config(page_title="Portfolio Image/CSV to Import CSV", layout="wide")

DEFAULT_TOTAL_CAD = 1_000_000.0

DEFAULT_PORTFOLIO = [
    ("CAD", "Encaisse", 1.0),
    ("CCL.B", "CCL Industrie", 1.5),
    ("TECK.B", "Teck ressources", 1.5),
    ("META", "Meta Platform", 1.5),
    ("ETN", "Eaton Corporation", 1.5),
    ("WSP", "WSP Global", 1.5),
    ("NTR", "Nutrien", 1.5),
    ("AVGO", "Broadcom Inc", 1.5),
    ("ATRL", "Groupe Atkinsrealis", 1.5),
    ("MCD", "Mcdonalds", 2.0),
    ("MRU", "Metro Inc", 2.0),
    ("JPM", "JP Morgan Chase", 2.0),
    ("NA", "Banque National du Canada", 2.0),
    ("NKE", "Nike Inc", 2.0),
    ("T", "Telus Corp", 2.0),
    ("UNH", "United Health Group", 2.0),
    ("MA", "Mastercard", 2.0),
    ("BCE", "BCE INC", 2.0),
    ("ARX", "ARC Ressources", 2.0),
    ("WCN", "Waste Connections Inc", 2.0),
    ("TFII", "TFI International Inc", 2.0),
    ("GSK", "GlaxoSmithKline", 2.0),
    ("CVE", "Cenovus Energy", 2.5),
    ("AAPL", "Apple Inc", 3.0),
    ("ENB", "Enbridge", 3.0),
    ("MSFT", "Microsoft", 3.0),
    ("RY", "Banque Royale du Canada", 3.0),
    ("TD", "Banque Toronto Dominion", 3.0),
    ("WMT", "Wallmart", 3.0),
    ("FLEM", "Franklin Emerging Market ETF", 3.0),
    ("ATD", "Alimentation Couche-Tard", 3.0),
    ("FGDL", "Franklin Gold ETF", 3.0),
    ("AMZN", "Amazon", 3.5),
    ("TSM", "Taiwan Semiconductor", 4.0),
    ("GOOGL", "Alphabet Inc", 4.0),
    ("BRK.B", "Berkshire Hathaway", 5.0),
    ("FHIS", "Franklin CND ultra short bond ETF", 7.5),
    ("EQY", "Franklin All Equity ETF", 7.5),
]

SAMPLE_COLUMNS = [
    "Date",
    "Type",
    "Figi",
    "Ticker",
    "MIC",
    "Listing Country",
    "Shares",
    "Cost Basis",
    "Exchange Rate",
    "Affect Cash",
]

TICKER_MAP = {
    "CCL.B": {"yf": "CCL.B.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "TECK.B": {"yf": "TECK-B.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "WSP": {"yf": "WSP.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "NTR": {"yf": "NTR.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "ATRL": {"yf": "ATRL.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "MRU": {"yf": "MRU.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "NA": {"yf": "NA.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "T": {"yf": "T.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "BCE": {"yf": "BCE.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "ARX": {"yf": "ARX.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "TFII": {"yf": "TFII.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "CVE": {"yf": "CVE.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "ENB": {"yf": "ENB.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "RY": {"yf": "RY.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "TD": {"yf": "TD.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "ATD": {"yf": "ATD.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "FLEM": {"yf": "FLEM.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "FGDL": {"yf": "FGDL.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "FHIS": {"yf": "FHIS.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "EQY": {"yf": "EQY.TO", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "META": {"yf": "META", "mic": "XNAS", "country": "US", "currency": "USD"},
    "ETN": {"yf": "ETN", "mic": "XNYS", "country": "US", "currency": "USD"},
    "AVGO": {"yf": "AVGO", "mic": "XNAS", "country": "US", "currency": "USD"},
    "MCD": {"yf": "MCD", "mic": "XNYS", "country": "US", "currency": "USD"},
    "JPM": {"yf": "JPM", "mic": "XNYS", "country": "US", "currency": "USD"},
    "NKE": {"yf": "NKE", "mic": "XNYS", "country": "US", "currency": "USD"},
    "UNH": {"yf": "UNH", "mic": "XNYS", "country": "US", "currency": "USD"},
    "MA": {"yf": "MA", "mic": "XNYS", "country": "US", "currency": "USD"},
    "WCN": {"yf": "WCN", "mic": "XNYS", "country": "CA", "currency": "USD"},
    "GSK": {"yf": "GSK", "mic": "XNYS", "country": "GB", "currency": "USD"},
    "AAPL": {"yf": "AAPL", "mic": "XNAS", "country": "US", "currency": "USD"},
    "MSFT": {"yf": "MSFT", "mic": "XNAS", "country": "US", "currency": "USD"},
    "WMT": {"yf": "WMT", "mic": "XNYS", "country": "US", "currency": "USD"},
    "AMZN": {"yf": "AMZN", "mic": "XNAS", "country": "US", "currency": "USD"},
    "TSM": {"yf": "TSM", "mic": "XNYS", "country": "TW", "currency": "USD"},
    "GOOGL": {"yf": "GOOGL", "mic": "XNAS", "country": "US", "currency": "USD"},
    "BRK.B": {"yf": "BRK-B", "mic": "XNYS", "country": "US", "currency": "USD"},
    "CAD": {"yf": None, "mic": "XOTC", "country": "CA", "currency": "CAD"},
}

OCR_ENGINE = None

@dataclass
class Holding:
    ticker: str
    name: str
    weight_pct: float


def init_state():
    if "holdings_df" not in st.session_state:
        st.session_state["holdings_df"] = pd.DataFrame(DEFAULT_PORTFOLIO, columns=["Ticker", "Name", "Weight %"])
    if "usd_cad" not in st.session_state:
        st.session_state["usd_cad"] = 1.37


def clean_weight(value: str) -> Optional[float]:
    if value is None:
        return None
    txt = str(value).strip().replace("%", "").replace(",", ".")
    txt = re.sub(r"[^0-9.\-]", "", txt)
    if not txt:
        return None
    try:
        return float(txt)
    except Exception:
        return None


def normalize_ticker(ticker: str) -> str:
    t = (ticker or "").upper().strip()
    t = t.replace(" ", "")
    t = t.replace("BRK/B", "BRK.B").replace("BRK-B", "BRK.B")
    t = t.replace("TECK-B", "TECK.B").replace("CCL-B", "CCL.B")
    return t


def parse_text_portfolio(raw_text: str) -> pd.DataFrame:
    rows: List[Tuple[str, str, float]] = []
    seen = set()
    for raw_line in raw_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        weight_match = re.search(r"(\d+[.,]?\d*)\s*%?$", line)
        if not weight_match:
            continue
        weight = clean_weight(weight_match.group(1))
        if weight is None:
            continue
        left = line[:weight_match.start()].strip()
        ticker_match = re.match(r"^([A-Z][A-Z0-9.\-]{0,9})\b", left)
        if not ticker_match:
            continue
        ticker = normalize_ticker(ticker_match.group(1))
        name = left[ticker_match.end():].strip(" -|:") or ticker
        key = (ticker, round(weight, 4))
        if key in seen:
            continue
        seen.add(key)
        rows.append((ticker, name, weight))
    df = pd.DataFrame(rows, columns=["Ticker", "Name", "Weight %"])
    return df


def image_to_text(image: Image.Image) -> str:
    global OCR_ENGINE
    if not OCR_AVAILABLE:
        return ""
    if OCR_ENGINE is None:
        OCR_ENGINE = RapidOCR()
    gray = ImageOps.grayscale(image)
    result, _ = OCR_ENGINE(gray)
    if not result:
        return ""
    return "\n".join([item[1] for item in result if item and len(item) > 1 and item[1]])


@st.cache_data(show_spinner=False)
def get_fx_usd_cad() -> float:
    try:
        fx = yf.Ticker("CADUSD=X")
        hist = fx.history(period="5d")
        if not hist.empty:
            cadusd = float(hist["Close"].dropna().iloc[-1])
            if cadusd > 0:
                return round(1 / cadusd, 6)
    except Exception:
        pass
    return 1.37


@st.cache_data(show_spinner=False)
def fetch_last_price(yf_symbol: str) -> Optional[float]:
    if not yf_symbol:
        return None
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="5d", auto_adjust=False)
        closes = hist["Close"].dropna()
        if not closes.empty:
            return float(closes.iloc[-1])
    except Exception:
        return None
    return None


def build_prices(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    out = df.copy()
    meta_rows = []
    for tkr in out["Ticker"]:
        meta = TICKER_MAP.get(tkr, {"yf": tkr, "mic": "", "country": "", "currency": "USD"})
        price = None if tkr == "CAD" else fetch_last_price(meta["yf"])
        meta_rows.append({
            "Yahoo Symbol": meta["yf"],
            "Currency": meta["currency"],
            "Price": price if price is not None else 0.0,
            "MIC": meta["mic"],
            "Listing Country": meta["country"],
            "Exchange Rate": 1.0 if meta["currency"] == "CAD" else usd_cad,
        })
    meta_df = pd.DataFrame(meta_rows)
    return pd.concat([out.reset_index(drop=True), meta_df], axis=1)


def allocate_portfolio(df: pd.DataFrame, total_cad: float) -> Tuple[pd.DataFrame, float]:
    out = df.copy()
    out["Target CAD"] = total_cad * out["Weight %"] / 100.0
    shares = []
    cost_basis = []
    for _, row in out.iterrows():
        if row["Ticker"] == "CAD":
            shares.append(0)
            cost_basis.append(0.0)
            continue
        px = float(row["Price"] or 0)
        fx = float(row["Exchange Rate"] or 1)
        if px <= 0 or fx <= 0:
            shares.append(0)
            cost_basis.append(0.0)
            continue
        whole_shares = int(row["Target CAD"] // (px * fx))
        shares.append(whole_shares)
        cost_basis.append(round(px, 6))
    out["Shares"] = shares
    out["Cost Basis"] = cost_basis
    out["Allocated CAD"] = out["Shares"] * out["Cost Basis"] * out["Exchange Rate"]
    invested = float(out.loc[out["Ticker"] != "CAD", "Allocated CAD"].sum())
    residual_cash = round(total_cad - invested, 2)
    out.loc[out["Ticker"] == "CAD", "Cost Basis"] = residual_cash
    out.loc[out["Ticker"] == "CAD", "Allocated CAD"] = residual_cash
    return out, residual_cash


def to_sample_csv(df: pd.DataFrame, as_of_date: str) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "Date": as_of_date,
            "Type": "BUY",
            "Figi": "",
            "Ticker": row["Ticker"],
            "MIC": row["MIC"],
            "Listing Country": row["Listing Country"],
            "Shares": row["Shares"],
            "Cost Basis": row["Cost Basis"],
            "Exchange Rate": row["Exchange Rate"],
            "Affect Cash": "TRUE",
        })
    return pd.DataFrame(rows, columns=SAMPLE_COLUMNS)


def csv_download_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


init_state()

st.title("Portfolio Image/CSV to Sample Import CSV")
st.caption("Upload an image, paste text, or upload CSV. Default base is C$1,000,000.")

with st.sidebar:
    total_cad = st.number_input("Base portfolio (CAD)", min_value=1000.0, value=float(DEFAULT_TOTAL_CAD), step=10000.0)
    if st.checkbox("Auto-fetch USD/CAD", value=True):
        st.session_state["usd_cad"] = get_fx_usd_cad()
    usd_cad = st.number_input("USD/CAD", min_value=0.5, max_value=3.0, value=float(st.session_state["usd_cad"]), step=0.01, format="%.6f")
    as_of_date = st.date_input("Trade date")

tab1, tab2, tab3 = st.tabs(["Image or Text", "CSV Upload", "Review and Export"])

with tab1:
    image_file = st.file_uploader("Upload image", type=["png", "jpg", "jpeg", "webp"])
    pasted_text = st.text_area("Or paste portfolio text", height=220)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load default portfolio"):
            st.session_state["holdings_df"] = pd.DataFrame(DEFAULT_PORTFOLIO, columns=["Ticker", "Name", "Weight %"])
            st.success("Default portfolio loaded.")
    with c2:
        if st.button("Parse image/text"):
            extracted = ""
            if image_file is not None:
                image = Image.open(image_file)
                st.image(image, use_container_width=True)
                extracted = image_to_text(image)
                if extracted:
                    st.text_area("OCR result", extracted, height=220)
            source = pasted_text.strip() or extracted
            parsed = parse_text_portfolio(source) if source else pd.DataFrame(columns=["Ticker", "Name", "Weight %"])
            if parsed.empty:
                st.warning("Could not parse rows reliably. You can still edit manually in the Review tab.")
            else:
                st.session_state["holdings_df"] = parsed
                st.success(f"Parsed {len(parsed)} rows.")
    if not OCR_AVAILABLE:
        st.info("Image OCR activates after installing requirements.")

with tab2:
    csv_file = st.file_uploader("Upload CSV", type=["csv"], key="csvup")
    if csv_file is not None:
        df_csv = pd.read_csv(csv_file)
        st.dataframe(df_csv, use_container_width=True)
        cols = list(df_csv.columns)
        if cols:
            ticker_col = st.selectbox("Ticker column", cols, index=0)
            name_col = st.selectbox("Name column", cols, index=min(1, len(cols)-1))
            weight_col = st.selectbox("Weight column", cols, index=min(2, len(cols)-1))
            if st.button("Load CSV"):
                mapped = pd.DataFrame({
                    "Ticker": df_csv[ticker_col].astype(str).map(normalize_ticker),
                    "Name": df_csv[name_col].astype(str),
                    "Weight %": df_csv[weight_col].map(clean_weight),
                }).dropna(subset=["Ticker", "Weight %"]).reset_index(drop=True)
                st.session_state["holdings_df"] = mapped
                st.success(f"Loaded {len(mapped)} rows.")

with tab3:
    edited = st.data_editor(
        st.session_state["holdings_df"],
        num_rows="dynamic",
        use_container_width=True,
        key="holdings_editor",
    )
    edited["Ticker"] = edited["Ticker"].astype(str).map(normalize_ticker)
    edited["Weight %"] = pd.to_numeric(edited["Weight %"], errors="coerce")
    edited = edited.dropna(subset=["Ticker", "Weight %"]).reset_index(drop=True)

    st.write(f"Weight total: {edited['Weight %'].sum():.2f}%")

    if st.button("Fetch prices"):
        st.session_state["priced_df"] = build_prices(edited, usd_cad)

    if "priced_df" in st.session_state:
        priced = st.data_editor(st.session_state["priced_df"], num_rows="dynamic", use_container_width=True, key="priced_editor")
        allocated, residual_cash = allocate_portfolio(priced, total_cad)
        sample_csv = to_sample_csv(allocated, str(as_of_date))

        c1, c2 = st.columns(2)
        c1.metric("Residual cash", f"C${residual_cash:,.2f}")
        c2.metric("Rows", len(sample_csv))

        st.dataframe(allocated[["Ticker", "Name", "Weight %", "Price", "Currency", "Exchange Rate", "Shares", "Allocated CAD"]], use_container_width=True)
        st.dataframe(sample_csv, use_container_width=True)

        st.download_button(
            "Download CSV",
            data=csv_download_bytes(sample_csv),
            file_name="portfolio_import_from_image_or_csv.csv",
            mime="text/csv",
        )

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            allocated.to_excel(writer, sheet_name="Allocation", index=False)
            sample_csv.to_excel(writer, sheet_name="Import CSV", index=False)
        excel_buffer.seek(0)
        st.download_button(
            "Download Excel summary",
            data=excel_buffer.getvalue(),
            file_name="portfolio_import_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
