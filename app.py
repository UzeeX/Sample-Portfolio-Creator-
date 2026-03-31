import csv
import io
import re
import urllib.parse
import urllib.request
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    from rapidocr_onnxruntime import RapidOCR

    OCR_AVAILABLE = True
except Exception:
    RapidOCR = None
    OCR_AVAILABLE = False


st.set_page_config(page_title="Portfolio Image/CSV to Sample Import CSV", layout="wide")

DEFAULT_TOTAL_CAD = 1_000_000.0

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
    "CCL.B": {"stooq": "ccl-b.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "TECK.B": {"stooq": "teck-b.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "WSP": {"stooq": "wsp.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "NTR": {"stooq": "ntr.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "ATRL": {"stooq": "atrl.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "MRU": {"stooq": "mru.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "NA": {"stooq": "na.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "T": {"stooq": "t.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "BCE": {"stooq": "bce.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "ARX": {"stooq": "arx.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "TFII": {"stooq": "tfii.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "CVE": {"stooq": "cve.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "ENB": {"stooq": "enb.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "RY": {"stooq": "ry.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "TD": {"stooq": "td.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "ATD": {"stooq": "atd.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "FLEM": {"stooq": "flem.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "FGDL": {"stooq": "fgdl.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "FHIS": {"stooq": "fhis.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "EQY": {"stooq": "eqy.ca", "mic": "XTSE", "country": "CA", "currency": "CAD"},
    "META": {"stooq": "meta.us", "mic": "XNAS", "country": "US", "currency": "USD"},
    "ETN": {"stooq": "etn.us", "mic": "XNYS", "country": "US", "currency": "USD"},
    "AVGO": {"stooq": "avgo.us", "mic": "XNAS", "country": "US", "currency": "USD"},
    "MCD": {"stooq": "mcd.us", "mic": "XNYS", "country": "US", "currency": "USD"},
    "JPM": {"stooq": "jpm.us", "mic": "XNYS", "country": "US", "currency": "USD"},
    "NKE": {"stooq": "nke.us", "mic": "XNYS", "country": "US", "currency": "USD"},
    "UNH": {"stooq": "unh.us", "mic": "XNYS", "country": "US", "currency": "USD"},
    "MA": {"stooq": "ma.us", "mic": "XNYS", "country": "US", "currency": "USD"},
    "WCN": {"stooq": "wcn.us", "mic": "XNYS", "country": "CA", "currency": "USD"},
    "GSK": {"stooq": "gsk.us", "mic": "XNYS", "country": "GB", "currency": "USD"},
    "AAPL": {"stooq": "aapl.us", "mic": "XNAS", "country": "US", "currency": "USD"},
    "MSFT": {"stooq": "msft.us", "mic": "XNAS", "country": "US", "currency": "USD"},
    "WMT": {"stooq": "wmt.us", "mic": "XNYS", "country": "US", "currency": "USD"},
    "AMZN": {"stooq": "amzn.us", "mic": "XNAS", "country": "US", "currency": "USD"},
    "TSM": {"stooq": "tsm.us", "mic": "XNYS", "country": "TW", "currency": "USD"},
    "GOOGL": {"stooq": "googl.us", "mic": "XNAS", "country": "US", "currency": "USD"},
    "BRK.B": {"stooq": "brk-b.us", "mic": "XNYS", "country": "US", "currency": "USD"},
    "CAD": {"stooq": None, "mic": "XOTC", "country": "CA", "currency": "CAD"},
}

PRICE_FALLBACKS = {
    "CAD": 1.0,
}


def init_state():
    if "holdings_df" not in st.session_state:
        st.session_state["holdings_df"] = pd.DataFrame(columns=["Ticker", "Name", "Weight %"])
    if "usd_cad" not in st.session_state:
        st.session_state["usd_cad"] = 1.37
    if "priced_df" not in st.session_state:
        st.session_state["priced_df"] = None
    if "ocr_text" not in st.session_state:
        st.session_state["ocr_text"] = ""


def clean_weight(value) -> Optional[float]:
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
    t = (ticker or "").upper().strip().replace(" ", "")
    t = t.replace("BRK/B", "BRK.B").replace("BRK-B", "BRK.B")
    t = t.replace("TECK-B", "TECK.B").replace("CCL-B", "CCL.B")
    t = t.replace("SHOPTO", "SHOP").replace("SHOP.TO", "SHOP")
    return t


def prettify_name(name: str, ticker: str) -> str:
    name = re.sub(r"\s+", " ", (name or "")).strip(" -|:")
    if not name:
        return ticker
    return name


def parse_text_portfolio(raw_text: str) -> pd.DataFrame:
    rows: List[Tuple[str, str, float]] = []
    seen = set()

    lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines()]
    lines = [line for line in lines if line]

    for i, line in enumerate(lines):
        working_line = line

        percent_match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", working_line)
        trailing_match = re.search(r"(\d+(?:[.,]\d+)?)\s*$", working_line)

        weight_match = percent_match or trailing_match

        # If no weight on this line, try next line
        if not weight_match and i + 1 < len(lines):
            combined = f"{working_line} {lines[i + 1]}"
            percent_match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", combined)
            trailing_match = re.search(r"(\d+(?:[.,]\d+)?)\s*$", combined)
            weight_match = percent_match or trailing_match
            if weight_match:
                working_line = combined

        if not weight_match:
            continue

        weight = clean_weight(weight_match.group(1))
        if weight is None or weight <= 0:
            continue
        if weight > 100:
            continue

        # Look for known mapped tickers first
        ticker = None
        for known in sorted(TICKER_MAP.keys(), key=len, reverse=True):
            if known == "CAD":
                continue
            if re.search(rf"\b{re.escape(known)}\b", working_line, re.IGNORECASE):
                ticker = known
                break

        # Generic ticker fallback
        if not ticker:
            generic = re.search(r"\b([A-Z]{1,5}(?:[.\-][A-Z])?)\b", working_line.upper())
            if generic:
                ticker = normalize_ticker(generic.group(1))

        if not ticker:
            continue

        # Remove ticker and weight to get a cleaner name
        name = working_line
        name = re.sub(rf"\b{re.escape(ticker)}\b", "", name, count=1, flags=re.IGNORECASE)
        name = re.sub(r"(\d+(?:[.,]\d+)?)\s*%?", "", name, count=1)
        name = prettify_name(name, ticker)

        key = (ticker, round(weight, 4))
        if key in seen:
            continue

        seen.add(key)
        rows.append((ticker, name, weight))

    df = pd.DataFrame(rows, columns=["Ticker", "Name", "Weight %"])

    if not df.empty:
        df = (
            df.groupby(["Ticker", "Name"], as_index=False)["Weight %"]
            .sum()
            .sort_values("Weight %", ascending=False)
            .reset_index(drop=True)
        )

    return df


def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    img = image.convert("RGB")
    img = ImageOps.exif_transpose(img)
    img = ImageOps.grayscale(img)

    w, h = img.size
    if max(w, h) < 1800:
        img = img.resize((w * 2, h * 2))

    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda p: 255 if p > 170 else 0)

    return img


def image_to_text(image: Image.Image) -> str:
    if not OCR_AVAILABLE:
        return ""

    try:
        engine = RapidOCR()
        processed = preprocess_image_for_ocr(image)
        result, _ = engine(processed)

        if not result:
            return ""

        lines = []
        for item in result:
            if item and len(item) > 1 and item[1]:
                txt = str(item[1]).strip()
                if txt:
                    lines.append(txt)

        return "\n".join(lines)
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def fetch_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/plain,text/csv,text/html,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


@st.cache_data(show_spinner=False)
def get_fx_usd_cad() -> float:
    try:
        url = "https://api.exchangerate.host/convert?from=USD&to=CAD&amount=1"
        text = fetch_text(url)
        m = re.search(r'"result"\s*:\s*([0-9.]+)', text)
        if m:
            value = float(m.group(1))
            if value > 0:
                return round(value, 6)
    except Exception:
        pass
    return 1.37


@st.cache_data(show_spinner=False)
def fetch_last_price_stooq(symbol: Optional[str]) -> Optional[float]:
    if not symbol:
        return None
    try:
        query = urllib.parse.quote(symbol.lower())
        url = f"https://stooq.com/q/d/l/?s={query}&i=d"
        text = fetch_text(url)
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows:
            return None
        last = rows[-1]
        close_val = last.get("Close") or last.get("close")
        if close_val and str(close_val).lower() != "null":
            px = float(close_val)
            if px > 0:
                return px
    except Exception:
        return None
    return None


def build_prices(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    out = df.copy()
    meta_rows = []

    for tkr in out["Ticker"]:
        meta = TICKER_MAP.get(
            tkr,
            {"stooq": None, "mic": "", "country": "", "currency": "USD"},
        )

        if tkr == "CAD":
            price = 1.0
        else:
            price = fetch_last_price_stooq(meta["stooq"])
            if price is None:
                price = PRICE_FALLBACKS.get(tkr, 0.0)

        meta_rows.append(
            {
                "Remote Symbol": meta["stooq"],
                "Currency": meta["currency"],
                "Price": price,
                "MIC": meta["mic"],
                "Listing Country": meta["country"],
                "Exchange Rate": 1.0 if meta["currency"] == "CAD" else usd_cad,
            }
        )

    return pd.concat([out.reset_index(drop=True), pd.DataFrame(meta_rows)], axis=1)


def allocate_portfolio(df: pd.DataFrame, total_cad: float):
    out = df.copy()
    out["Target CAD"] = total_cad * out["Weight %"] / 100.0

    shares = []
    cost_basis = []

    for _, row in out.iterrows():
        if row["Ticker"] == "CAD":
            shares.append(0)
            cost_basis.append(0.0)
            continue

        px = float(row.get("Price", 0) or 0)
        fx = float(row.get("Exchange Rate", 1) or 1)

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

    cash_mask = out["Ticker"] == "CAD"
    if cash_mask.any():
        out.loc[cash_mask, "Shares"] = 0
        out.loc[cash_mask, "Cost Basis"] = residual_cash
        out.loc[cash_mask, "Allocated CAD"] = residual_cash
    else:
        cash_row = pd.DataFrame(
            [
                {
                    "Ticker": "CAD",
                    "Name": "Cash",
                    "Weight %": 0.0,
                    "Target CAD": 0.0,
                    "Remote Symbol": None,
                    "Currency": "CAD",
                    "Price": 1.0,
                    "MIC": "XOTC",
                    "Listing Country": "CA",
                    "Exchange Rate": 1.0,
                    "Shares": 0,
                    "Cost Basis": residual_cash,
                    "Allocated CAD": residual_cash,
                }
            ]
        )
        out = pd.concat([out, cash_row], ignore_index=True)

    return out, residual_cash


def to_sample_csv(df: pd.DataFrame, as_of_date: str) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
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
            }
        )
    return pd.DataFrame(rows, columns=SAMPLE_COLUMNS)


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


init_state()

st.title("Portfolio Image/CSV to Sample Import CSV")
st.caption("Starts empty. Upload an image, paste text, or upload CSV. Base portfolio defaults to C$1,000,000.")

if not OCR_AVAILABLE:
    st.warning("OCR package is not installed. Image upload works, but text extraction from images is disabled.")

with st.sidebar:
    total_cad = st.number_input(
        "Base portfolio (CAD)",
        min_value=1000.0,
        value=float(DEFAULT_TOTAL_CAD),
        step=10000.0,
        format="%.2f",
    )

    if st.checkbox("Auto-fetch USD/CAD", value=True):
        st.session_state["usd_cad"] = get_fx_usd_cad()

    usd_cad = st.number_input(
        "USD/CAD",
        min_value=0.5,
        max_value=3.0,
        value=float(st.session_state["usd_cad"]),
        step=0.01,
        format="%.6f",
    )

    as_of_date = st.date_input("Trade date")

tab1, tab2, tab3 = st.tabs(["Image / Text", "CSV Upload", "Review & Export"])

with tab1:
    uploaded_image = st.file_uploader(
        "Upload screenshot/image",
        type=["png", "jpg", "jpeg", "webp"],
        key="img_upl",
    )
    pasted_text = st.text_area("Or paste text directly", height=220)

    if st.button("Parse image / text"):
        parsed_df = pd.DataFrame(columns=["Ticker", "Name", "Weight %"])
        ocr_text = ""

        if uploaded_image is not None:
            image = Image.open(uploaded_image)
            st.image(image, caption="Uploaded image", use_container_width=True)

            if OCR_AVAILABLE:
                ocr_text = image_to_text(image)
                st.session_state["ocr_text"] = ocr_text

        source_text = pasted_text.strip() if pasted_text.strip() else ocr_text

        if source_text:
            parsed_df = parse_text_portfolio(source_text)
            if parsed_df.empty:
                st.warning("Nothing reliable was parsed. You can still edit the table manually in the Review tab.")
            else:
                st.success(f"Parsed {len(parsed_df)} holding(s).")
                st.session_state["holdings_df"] = parsed_df
        else:
            st.warning("No usable text found from image or pasted text.")

    if st.session_state.get("ocr_text"):
        st.text_area("OCR text", value=st.session_state["ocr_text"], height=220)

with tab2:
    uploaded_csv = st.file_uploader("Upload CSV", type=["csv"], key="csv_upl")

    if uploaded_csv is not None:
        try:
            df_csv = pd.read_csv(uploaded_csv)
            lower_map = {c.lower().strip(): c for c in df_csv.columns}

            ticker_col = lower_map.get("ticker")
            name_col = lower_map.get("name")
            weight_col = lower_map.get("weight %") or lower_map.get("weight") or lower_map.get("portfolio %")

            if ticker_col and weight_col:
                clean_df = pd.DataFrame(
                    {
                        "Ticker": df_csv[ticker_col].astype(str).map(normalize_ticker),
                        "Name": df_csv[name_col].astype(str) if name_col else df_csv[ticker_col].astype(str),
                        "Weight %": df_csv[weight_col].map(clean_weight),
                    }
                )
                clean_df = clean_df.dropna(subset=["Ticker", "Weight %"])
                clean_df = clean_df[clean_df["Ticker"].astype(str).str.len() > 0].reset_index(drop=True)

                st.session_state["holdings_df"] = clean_df
                st.success(f"Loaded {len(clean_df)} holding(s) from CSV.")
            else:
                st.error("CSV must contain at least Ticker and Weight columns.")
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

with tab3:
    st.subheader("Holdings")

    holdings_df = st.session_state["holdings_df"].copy()
    edited_df = st.data_editor(
        holdings_df,
        num_rows="dynamic",
        use_container_width=True,
        key="holdings_editor",
    )
    st.session_state["holdings_df"] = edited_df

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Fetch prices & allocate"):
            base_df = st.session_state["holdings_df"].copy()

            if base_df.empty:
                st.warning("Please add at least one holding first.")
            else:
                base_df["Ticker"] = base_df["Ticker"].astype(str).map(normalize_ticker)
                base_df["Weight %"] = base_df["Weight %"].map(clean_weight)
                base_df = base_df.dropna(subset=["Ticker", "Weight %"]).reset_index(drop=True)

                priced_df = build_prices(base_df, usd_cad)
                allocated_df, residual_cash = allocate_portfolio(priced_df, total_cad)
                st.session_state["priced_df"] = allocated_df

                st.success(f"Done. Residual cash: C${residual_cash:,.2f}")

    with col_b:
        if st.button("Clear all"):
            st.session_state["holdings_df"] = pd.DataFrame(columns=["Ticker", "Name", "Weight %"])
            st.session_state["priced_df"] = None
            st.session_state["ocr_text"] = ""
            st.rerun()

    if st.session_state["priced_df"] is not None:
        st.subheader("Priced / Allocated")
        st.dataframe(st.session_state["priced_df"], use_container_width=True)

        sample_df = to_sample_csv(st.session_state["priced_df"], str(as_of_date))
        st.subheader("Sample Import CSV Preview")
        st.dataframe(sample_df, use_container_width=True)

        st.download_button(
            "Download sample_import.csv",
            data=csv_bytes(sample_df),
            file_name="sample_import.csv",
            mime="text/csv",
        )
