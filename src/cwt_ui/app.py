# src/cwt_ui/app.py  (run: streamlit run src/cwt_ui/app.py)
from __future__ import annotations

import os
import sys
from pathlib import Path
import importlib
import pandas as pd
import streamlit as st

# === Streamlit config ===
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

# === Scans adapter (LIVE; no CSV) ===
scans = try_import("cwt_ui.services.scans")

# === UI fallbacks ===
def _fb_currency(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return str(x)

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

# === Helpers ===
def add_status(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "recommendation" in out.columns and "status" not in out.columns:
        out["status"] = out["recommendation"].astype(str).str.upper().map(
            lambda x: "🟢 OK" if x == "OK" else "🔴 Action"
        )
    return out

def compute_summary(ec2_df: pd.DataFrame, s3_df: pd.DataFrame):
    idle = 0; waste = 0.0; cold = 0.0
    if ec2_df is not None and not ec2_df.empty:
        if "recommendation" in ec2_df.columns:
            m = ~ec2_df["recommendation"].astype(str).str.upper().eq("OK")
        else:
            m = ec2_df.index == ec2_df.index  # treat all as actionable if missing column
        idle = int(m.sum())
        if "monthly_cost_usd" in ec2_df.columns:
            waste = float(ec2_df.loc[m, "monthly_cost_usd"].fillna(0).sum())
    if s3_df is not None and not s3_df.empty and "standard_cold_gb" in s3_df.columns:
        cold = float(s3_df["standard_cold_gb"].fillna(0).sum())
    return idle, waste, cold

def run_live_scans(region: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if scans is None or not hasattr(scans, "run_all_scans"):
        st.error("Scans adapter not found: cwt_ui.services.scans.run_all_scans")
        return pd.DataFrame(), pd.DataFrame()
    try:
        # Prepare optional session-scoped AWS credential overrides
        creds = None
        if st.session_state.get("aws_override_enabled"):
            ak = st.session_state.get("aws_access_key_id", "").strip()
            sk = st.session_state.get("aws_secret_access_key", "").strip()
            rg = st.session_state.get("aws_default_region", "").strip()
            stoken = st.session_state.get("aws_session_token", "").strip()
            creds = {
                k: v
                for k, v in {
                    "AWS_ACCESS_KEY_ID": ak,
                    "AWS_SECRET_ACCESS_KEY": sk,
                    "AWS_DEFAULT_REGION": rg or (region or ""),
                    "AWS_SESSION_TOKEN": stoken,
                }.items()
                if v
            }

        ec2_df, s3_df = scans.run_all_scans(region=region, aws_credentials=creds)  # type: ignore
        # Stamp scan time
        import datetime as _dt
        scanned_at = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        st.session_state["last_scan_at"] = scanned_at
        def _stamp(df: pd.DataFrame) -> pd.DataFrame:
            if df is None or df.empty:
                return pd.DataFrame()
            out = df.copy()
            out["scanned_at"] = scanned_at
            return out
        return add_status(_stamp(ec2_df)), add_status(_stamp(s3_df))
    except Exception as e:
        st.warning(f"Live scan failed: {e}")
        return pd.DataFrame(), pd.DataFrame()

# === App ===
st.title("Cloud Waste Tracker 💸")

# Session defaults
st.session_state.setdefault("ec2_df", pd.DataFrame())
st.session_state.setdefault("s3_df", pd.DataFrame())
st.session_state.setdefault("region", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

with st.sidebar:
    st.header("Scan Controls")

    # Region selector
    st.session_state["region"] = st.text_input(
        "AWS Region",
        value=st.session_state["region"],
        help="Defaults to AWS_DEFAULT_REGION; e.g., us-east-1"
    )

    # Actions
    if st.button("Run Live Scan"):
        ec2_df, s3_df = run_live_scans(st.session_state["region"])
        st.session_state["ec2_df"] = ec2_df
        st.session_state["s3_df"]  = s3_df

    st.caption(f"Last scan: {st.session_state.get('last_scan_at','-')}")
    st.divider()
    st.caption("Use the Pages sidebar to navigate: Dashboard, EC2, S3, Settings.")

# Optional auto-run is disabled by default to avoid blocking app startup in deployments.
# Enable by setting env CWT_AUTO_SCAN_ON_START=true
auto_scan = os.getenv("CWT_AUTO_SCAN_ON_START", "false").strip().lower() == "true"
if auto_scan and st.session_state["ec2_df"].empty and st.session_state["s3_df"].empty:
    with st.spinner("Running initial live scan..."):
        ec2_df, s3_df = run_live_scans(st.session_state["region"])
        st.session_state["ec2_df"] = ec2_df
        st.session_state["s3_df"]  = s3_df

st.write("Welcome. Use the Pages sidebar to access Dashboard, EC2, S3, and Settings.")



