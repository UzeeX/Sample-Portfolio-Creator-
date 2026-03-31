import math
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Portfolio to Sample CSV", layout="wide")

# Optional dependency at runtime; app still works with manual prices if unavailable.
try:
    import yfinance as yf
except Exception:
    yf = None

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
    ("WCN", "Waste Connnections Inc", 2.0),
    ("TFII", "TFI International Inc", 2.0),
    ("GSK", "GlaxoSmithKline", 2.0),
    ("CVE", "Cenovus Energy", 2.5),
    ("AAPL", "Apple Inc", 3.0),
    ("ENB", "Enbridge", 3.0),
    ("MSFT", "Microsoft", 3.0),
    ("RY", "Banque Royale du Canada", 3.0),
    ("TD", "Banque Toronto Dominium", 3.0),
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

CA_TICKERS = {
    "CCL.B", "TECK.B", "WSP", "NTR", "ATRL", "MRU", "NA", "T", "BCE", "ARX", "TFII",
    "CVE", "ENB", "RY", "TD", "ATD", "FHIS", "EQY"
}
US_TICKERS = {
    "META", "ETN", "AVGO", "MCD", "JPM", "NKE", "UNH", "MA", "WCN", "GSK", "AAPL",
    "MSFT", "WMT", "FLEM", "FGDL", "AMZN", "TSM", "GOOGL", "BRK.B"
}
ETF_ARCA = {"FLEM", "FGDL"}


def default_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_PORTFOLIO, columns=["Ticker", "Name", "Weight %"])


def clean_weight(x) -> float:
    if pd.isna(x):
        return 0.0
    if isinstance(x, str):
        x = x.replace("%", "").replace(",", ".").strip()
    return float(x)


def classify_ticker(ticker: str):
    t = str(ticker).strip().upper()
    if t == "CAD":
        return {"country": "CA", "mic": "XCAD", "is_us": False}
    if t in CA_TICKERS:
        return {"country": "CA", "mic": "XTSE", "is_us": False}
    if t in ETF_ARCA:
        return {"country": "US", "mic": "ARCX", "is_us": True}
    if t in US_TICKERS:
        nyse = {"ETN", "MCD", "JPM", "NKE", "UNH", "MA", "WCN", "GSK", "WMT", "TSM", "BRK.B"}
        return {"country": "US", "mic": "XNYS" if t in nyse else "XNAS", "is_us": True}
    # Fallback: plain heuristic
    if "." in t:
        return {"country": "CA", "mic": "XTSE", "is_us": False}
    return {"country": "US", "mic": "XNAS", "is_us": True}


def yf_symbol(ticker: str, country: str) -> str:
    t = ticker.upper().strip()
    if country == "CA":
        return (
            t.replace(".B", "-B") + ".TO"
            if t.endswith(".B") else t + ".TO"
        )
    # US special cases
    mapping = {"BRK.B": "BRK-B", "META": "META", "GOOGL": "GOOGL"}
    return mapping.get(t, t)


def fetch_last_prices(df: pd.DataFrame):
    prices = {}
    fx = None
    if yf is None:
        return prices, fx

    try:
        fx_hist = yf.Ticker("CADUSD=X").history(period="5d", auto_adjust=False)
        if not fx_hist.empty:
            fx = float(fx_hist["Close"].dropna().iloc[-1])
    except Exception:
        fx = None

    for t in df["Ticker"].astype(str):
        if t.upper() == "CAD":
            continue
        meta = classify_ticker(t)
        symbol = yf_symbol(t, meta["country"])
        try:
            hist = yf.Ticker(symbol).history(period="5d", auto_adjust=False)
            if not hist.empty:
                prices[t.upper()] = float(hist["Close"].dropna().iloc[-1])
        except Exception:
            pass
    return prices, fx


def build_import(df: pd.DataFrame, trade_date: date, base_cad: float, fx_cadusd: float, manual_prices: dict):
    rows = []
    residual_cash = 0.0

    df2 = df.copy()
    df2["Ticker"] = df2["Ticker"].astype(str).str.strip().str.upper()
    df2["Weight %"] = df2["Weight %"].apply(clean_weight)

    for _, r in df2.iterrows():
        ticker = r["Ticker"]
        weight = float(r["Weight %"])
        target_cad = base_cad * weight / 100.0

        if ticker == "CAD":
            residual_cash += target_cad
            continue

        meta = classify_ticker(ticker)
        price = manual_prices.get(ticker)
        if not price or price <= 0:
            continue

        if meta["is_us"]:
            # fx_cadusd = USD per 1 CAD. Convert CAD target to USD before sizing.
            shares = math.floor((target_cad * fx_cadusd) / price)
            exchange_rate = fx_cadusd
            spent_cad = (shares * price) / fx_cadusd if shares > 0 else 0.0
        else:
            shares = math.floor(target_cad / price)
            exchange_rate = None
            spent_cad = shares * price if shares > 0 else 0.0

        residual_cash += max(target_cad - spent_cad, 0.0)

        if shares <= 0:
            continue

        rows.append({
            "Date": trade_date.isoformat(),
            "Type": "buy",
            "Figi": "",
            "Ticker": ticker,
            "MIC": meta["mic"],
            "Listing Country": meta["country"],
            "Shares": int(shares),
            "Cost Basis": round(price, 4),
            "Exchange Rate": round(exchange_rate, 6) if exchange_rate else "",
            "Affect Cash": True,
        })

    out = pd.DataFrame(rows, columns=SAMPLE_COLUMNS)
    summary = pd.DataFrame({
        "Residual Cash CAD": [round(residual_cash, 2)],
        "Total Invested CAD": [round(base_cad - residual_cash, 2)],
        "Base CAD": [round(base_cad, 2)],
    })
    return out, summary


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


st.title("Portfolio to Sample CSV")
st.caption("Builds an import file in the same structure as your sample, using C$1,000,000 by default.")

with st.sidebar:
    st.header("Settings")
    trade_date = st.date_input("Trade date", value=date.today())
    base_cad = st.number_input("Base portfolio (CAD)", min_value=1_000.0, value=1_000_000.0, step=10_000.0)
    fx_cadusd = st.number_input(
        "CAD/USD exchange rate",
        min_value=0.50,
        max_value=1.50,
        value=0.73,
        step=0.0001,
        help="Use USD per 1 CAD, like the sample file.",
    )
    st.markdown("---")
    auto_fetch = st.checkbox("Try to fetch latest prices with yfinance", value=True)

st.subheader("1) Portfolio weights")
portfolio_df = st.data_editor(
    default_df(),
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Ticker": st.column_config.TextColumn(required=True),
        "Name": st.column_config.TextColumn(required=False),
        "Weight %": st.column_config.NumberColumn(format="%.2f"),
    },
)

uploaded = st.file_uploader("Or upload a CSV with columns like Ticker / Weight %", type=["csv"])
if uploaded is not None:
    try:
        up = pd.read_csv(uploaded)
        cols = {c.lower().strip(): c for c in up.columns}
        ticker_col = cols.get("ticker") or cols.get("symbol")
        weight_col = cols.get("weight %") or cols.get("weight") or cols.get("allocation")
        name_col = cols.get("name") or cols.get("company")
        if ticker_col and weight_col:
            portfolio_df = pd.DataFrame({
                "Ticker": up[ticker_col],
                "Name": up[name_col] if name_col else "",
                "Weight %": up[weight_col],
            })
            st.success("Uploaded portfolio loaded.")
            st.dataframe(portfolio_df, use_container_width=True)
        else:
            st.warning("Upload needs at least a ticker column and a weight column.")
    except Exception as e:
        st.error(f"Could not read upload: {e}")

st.subheader("2) Prices")
prices = {}
auto_fx = None
if auto_fetch:
    with st.spinner("Fetching prices..."):
        prices, auto_fx = fetch_last_prices(portfolio_df)
    if auto_fx:
        fx_cadusd = auto_fx
        st.info(f"Auto-updated CAD/USD to {fx_cadusd:.6f}")

price_rows = []
for t in portfolio_df["Ticker"].astype(str).str.upper().str.strip():
    if t == "CAD" or not t:
        continue
    meta = classify_ticker(t)
    price_rows.append({
        "Ticker": t,
        "Country": meta["country"],
        "MIC": meta["mic"],
        "Last Price": prices.get(t, None),
    })

price_df = pd.DataFrame(price_rows).drop_duplicates(subset=["Ticker"])
price_df = st.data_editor(
    price_df,
    num_rows="fixed",
    use_container_width=True,
    column_config={"Last Price": st.column_config.NumberColumn(format="%.4f")},
    key="price_editor",
)

manual_prices = {str(r["Ticker"]).upper(): float(r["Last Price"]) for _, r in price_df.iterrows() if pd.notna(r["Last Price"])}

missing = [t for t in portfolio_df["Ticker"].astype(str).str.upper() if t != "CAD" and t not in manual_prices]
if missing:
    st.warning("Missing prices for: " + ", ".join(sorted(set(missing))))

st.subheader("3) Build import file")
if st.button("Generate sample-format CSV", type="primary"):
    import_df, summary_df = build_import(portfolio_df, trade_date, float(base_cad), float(fx_cadusd), manual_prices)

    if import_df.empty:
        st.error("No rows were generated. Add prices for the missing tickers and try again.")
    else:
        st.success("Import file generated.")
        c1, c2 = st.columns([2, 1])
        with c1:
            st.dataframe(import_df, use_container_width=True)
        with c2:
            st.dataframe(summary_df, use_container_width=True)

        st.download_button(
            "Download import CSV",
            data=to_csv_bytes(import_df),
            file_name="portfolio_import_sample_format.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download summary CSV",
            data=to_csv_bytes(summary_df),
            file_name="portfolio_import_summary.csv",
            mime="text/csv",
        )

st.markdown("---")
st.markdown("**Notes**")
st.markdown(
    "- The app keeps the exact sample columns.  \n"
    "- U.S. rows get an exchange rate; Canadian rows leave it blank.  \n"
    "- Share counts are rounded down to whole shares. Any leftover amount stays as residual cash in the summary.  \n"
    "- You can overwrite any fetched price before generating the file."
)
