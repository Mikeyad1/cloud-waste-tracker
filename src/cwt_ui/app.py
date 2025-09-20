# app.py  (run: streamlit run src\cwt_ui\app.py)
from __future__ import annotations
import sys
from pathlib import Path
import importlib
import pandas as pd
import streamlit as st

# === Streamlit config (חייב ראשון) ===
st.set_page_config(page_title="Cloud Waste Tracker", page_icon="💸", layout="wide")

# === Locate repo root & src ===
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR
for p in [APP_DIR, *APP_DIR.parents]:
    if (p / "src").exists():
        REPO_ROOT = p
        break

SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# === Safe import helper ===
def try_import(modpath: str):
    try:
        return importlib.import_module(modpath)
    except Exception:
        return None

# === UI modules (optional) ===
cards      = try_import("cwt_ui.components.cards")
tables     = try_import("cwt_ui.components.tables")
formatters = try_import("cwt_ui.services.formatters")
page_dash  = try_import("cwt_ui.pages.1_Dashboard")
page_ec2   = try_import("cwt_ui.pages.2_EC2")
page_s3    = try_import("cwt_ui.pages.3_S3")
page_set   = try_import("cwt_ui.pages.9_Settings")

# === Core scanners (your code) ===
ec2_scanner = try_import("cloud_waste_tracker.scanners.ec2_scanner")   # run(region=...) writes CSV :contentReference[oaicite:2]{index=2}
s3_scanner  = try_import("cloud_waste_tracker.scanners.s3_scanner")    # run(days_cold=...) writes CSV :contentReference[oaicite:3]{index=3}
utils_mod   = try_import("cloud_waste_tracker.utils.utils")            # optional: path_waste_csv()/path_s3_csv()

# === CSV paths (from utils if קיימים; אחרת fallback לשמות המוכרים) ===
if utils_mod and hasattr(utils_mod, "path_waste_csv"):
    DEFAULT_EC2_CSV = Path(str(utils_mod.path_waste_csv()))
else:
    DEFAULT_EC2_CSV = REPO_ROOT / "waste_report.csv"

if utils_mod and hasattr(utils_mod, "path_s3_csv"):
    DEFAULT_S3_CSV = Path(str(utils_mod.path_s3_csv()))
else:
    DEFAULT_S3_CSV = REPO_ROOT / "s3_waste_report.csv"

# debug (optional)
st.sidebar.caption(f"Repo: {REPO_ROOT}")
st.sidebar.caption(f"EC2 CSV: {DEFAULT_EC2_CSV.name} | S3 CSV: {DEFAULT_S3_CSV.name}")

# === UI fallbacks (אם עוד לא יישמת cwt_ui/...) ===
def _fb_currency(x):
    try: return f"${float(x):,.2f}"
    except Exception: return str(x)

if formatters is None or not hasattr(formatters, "currency"):
    class _Fmt:
        @staticmethod
        def currency(x): return _fb_currency(x)
        @staticmethod
        def percent(x, d: int = 2):
            try: return f"{float(x):.{d}f}%"
            except Exception: return str(x)
        @staticmethod
        def human_gb(x, d: int = 2):
            try: return f"{float(x):.{d}f} GB"
            except Exception: return str(x)
    formatters = _Fmt()

if cards is None or not hasattr(cards, "metric"):
    class _Cards:
        @staticmethod
        def metric(label, value, help_text=None):
            st.metric(label, value, help=help_text)
    cards = _Cards()

if tables is None or not hasattr(tables, "render"):
    class _Tables:
        @staticmethod
        def render(df: pd.DataFrame, **_):
            st.dataframe(df, use_container_width=True)
    tables = _Tables()

# === IO helpers ===
def load_csv_safe(path: Path) -> pd.DataFrame:
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception as e:
            st.error(f"Failed reading {path.name}: {e}")
    return pd.DataFrame()

def add_status(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    out = df.copy()
    if "recommendation" in out.columns and "status" not in out.columns:
        out["status"] = out["recommendation"].astype(str).str.upper().map(
            lambda x: "🟢 OK" if x == "OK" else "🔴 Action"
        )
    return out

def compute_summary(ec2_df: pd.DataFrame, s3_df: pd.DataFrame):
    idle = 0; waste = 0.0; cold = 0.0
    if ec2_df is not None and not ec2_df.empty:
        m = ~ec2_df["recommendation"].astype(str).str.upper().eq("OK")
        idle = int(m.sum())
        if "monthly_cost_usd" in ec2_df.columns:
            waste = float(ec2_df.loc[m, "monthly_cost_usd"].fillna(0).sum())
    if s3_df is not None and not s3_df.empty and "standard_cold_gb" in s3_df.columns:
        cold = float(s3_df["standard_cold_gb"].fillna(0).sum())
    return idle, waste, cold

# === Run scans (write CSV) then load ===
def run_scans_and_load() -> tuple[pd.DataFrame, pd.DataFrame]:
    # run() functions write the CSVs; they don't return DataFrame. :contentReference[oaicite:4]{index=4} :contentReference[oaicite:5]{index=5}
    if ec2_scanner and hasattr(ec2_scanner, "run"):
        try:
            ec2_scanner.run()  # region נקבע מתוך utils/ENV בקוד שלך
        except Exception as e:
            st.warning(f"EC2 scan failed: {e}")
    if s3_scanner and hasattr(s3_scanner, "run"):
        try:
            s3_scanner.run()
        except Exception as e:
            st.warning(f"S3 scan failed: {e}")

    ec2_df = load_csv_safe(DEFAULT_EC2_CSV)
    s3_df  = load_csv_safe(DEFAULT_S3_CSV)
    return ec2_df, s3_df

def refresh_data(run_scan: bool):
    if run_scan:
        ec2_df, s3_df = run_scans_and_load()
    else:
        ec2_df = load_csv_safe(DEFAULT_EC2_CSV)
        s3_df  = load_csv_safe(DEFAULT_S3_CSV)

    st.session_state["ec2_df"] = add_status(ec2_df)
    st.session_state["s3_df"]  = add_status(s3_df)

# === App ===
st.title("Cloud Waste Tracker 💸")

st.session_state.setdefault("ec2_df", None)
st.session_state.setdefault("s3_df", None)

with st.sidebar:
    st.header("Controls")
    if st.button("Run Scan (from scanners)"):
        refresh_data(run_scan=True)
    if st.button("Reload from CSV"):
        refresh_data(run_scan=False)
    st.divider()
    page = st.radio("Pages", ["Dashboard", "EC2", "S3", "Settings"])

# first load
if st.session_state["ec2_df"] is None and st.session_state["s3_df"] is None:
    refresh_data(run_scan=False)

ec2_df = st.session_state.get("ec2_df") if st.session_state.get("ec2_df") is not None else pd.DataFrame()
s3_df  = st.session_state.get("s3_df")  if st.session_state.get("s3_df")  is not None else pd.DataFrame()

# === Routing ===
if page == "Dashboard":
    if page_dash and hasattr(page_dash, "render"):
        page_dash.render(ec2_df, s3_df, cards, tables, formatters)  # :contentReference[oaicite:6]{index=6}
    else:
        c1, c2, c3 = st.columns(3)
        idle, waste, cold = compute_summary(ec2_df, s3_df)
        with c1: cards.metric("Idle EC2 (est.)", str(idle))
        with c2: cards.metric("Est. Monthly Waste", formatters.currency(waste))
        with c3: cards.metric("S3 Cold GB", f"{cold:,.2f}")
        st.subheader("EC2 (Top by Monthly Cost)")
        if not ec2_df.empty:
            cols = [c for c in ["status","instance_id","name","instance_type","region","avg_cpu_7d","monthly_cost_usd","recommendation"] if c in ec2_df.columns]
            df = ec2_df[cols]
            if "monthly_cost_usd" in df.columns: df = df.sort_values("monthly_cost_usd", ascending=False)
            tables.render(df, column_order=cols)
        else:
            st.info("No EC2 data.")
        st.divider()
        st.subheader("S3 Summary")
        if not s3_df.empty:
            cols = [c for c in ["status","bucket","region","size_total_gb","objects_total","standard_cold_gb","standard_cold_objects","lifecycle_defined","recommendation","notes"] if c in s3_df.columns]
            tables.render(s3_df[cols], column_order=cols)
        else:
            st.info("No S3 data.")

elif page == "EC2":
    if page_ec2 and hasattr(page_ec2, "render"):
        page_ec2.render(ec2_df, tables, formatters)  # :contentReference[oaicite:7]{index=7}
    else:
        st.header("EC2")
        if not ec2_df.empty:
            cols = [c for c in ["status","instance_id","name","instance_type","region","avg_cpu_7d","monthly_cost_usd","recommendation"] if c in ec2_df.columns]
            tables.render(ec2_df[cols], column_order=cols)
        else:
            st.info("No EC2 data.")

elif page == "S3":
    if page_s3 and hasattr(page_s3, "render"):
        page_s3.render(s3_df, tables, formatters)  # :contentReference[oaicite:8]{index=8}
    else:
        st.header("S3")
        if not s3_df.empty:
            cols = [c for c in ["status","bucket","region","size_total_gb","objects_total","standard_cold_gb","standard_cold_objects","lifecycle_defined","recommendation","notes"] if c in s3_df.columns]
            tables.render(s3_df[cols], column_order=cols)
        else:
            st.info("No S3 data.")
else:
    if page_set and hasattr(page_set, "render"):
        page_set.render()  # :contentReference[oaicite:9]{index=9}
    else:
        st.header("Settings")
        st.write("Auth/Stripe/Scheduler – coming soon.")
        st.caption(f"CSV defaults: {DEFAULT_EC2_CSV.name}, {DEFAULT_S3_CSV.name}")
