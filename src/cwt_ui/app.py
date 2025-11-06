# src/cwt_ui/app.py  (run: streamlit run src/cwt_ui/app.py)
from __future__ import annotations

import os
import sys
from pathlib import Path
import importlib
import pandas as pd
import streamlit as st

# === Streamlit config ===
st.set_page_config(
    page_title="Cloud Waste Tracker", 
    page_icon="💸", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure sidebar is always expanded and content aligns properly
if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"

# Simple layout fix - only adjust padding, don't override margins
st.markdown("""
<style>
    .main .block-container {
        padding-left: 1rem;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Load .env file first (before checking APP_ENV)
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file from project root
except ImportError:
    # dotenv not installed, that's okay
    pass

# Apply layout fixes inline
def apply_debug_utilities():
    """Apply debug utilities if in development mode."""
    # Import settings from new config system
    try:
        from config.factory import settings
        DEBUG_MODE = settings.DEBUG
        APP_ENV = settings.APP_ENV
    except ImportError:
        # Fallback to old method if config not available
        import os
        APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
        DEBUG_MODE = APP_ENV == "development"
    
    def debug_write(message: str):
        """Debug messages disabled - no-op function"""
        pass  # Debug messages removed from UI
    
    return debug_write, APP_ENV

debug_write, APP_ENV = apply_debug_utilities()

# Use APP_ENV from settings (already loaded in apply_debug_utilities)
# Only override if settings import failed
if APP_ENV is None:
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

# Create database tables on startup (production safety)
if APP_ENV == "production":
    try:
        from db.db import engine
        from db.models import Base
        Base.metadata.create_all(engine)
        print("✅ Database tables ensured on startup")
    except Exception as e:
        print(f"⚠️ Database table creation failed: {e}")

# Debug: Show environment detection (temporary)
debug_write(f"🔍 **ENV DEBUG:** APP_ENV='{APP_ENV}'")

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
# Note: Page modules (Dashboard, EC2, S3, AWS_Setup) are auto-discovered by Streamlit
# from the pages/ directory. Do not import them here as it causes them to render.

# === Scans adapter (ENHANCED; with clear recommendations) ===
scans = try_import("cwt_ui.services.enhanced_scans")
if scans is None:
    # Fallback to basic scans
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
        def percent(x):
            try: return f"{float(x):.1f}%"
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

def run_live_scans(region: str | List[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run AWS scans across one or more regions.
    
    Args:
        region: Can be:
            - None: Auto-discover and scan all enabled regions (default)
            - Single region string (e.g., "us-east-1")
            - List of regions (e.g., ["us-east-1", "eu-west-1"])
    
    Returns:
        Tuple of (EC2 DataFrame, S3 DataFrame) with results from all scanned regions
    """
    debug_write("🔍 **DEBUG:** run_live_scans() called")
    
    # If no region specified, use auto-discovery from session state or default to None
    if region is None:
        # Check if there's a scan_regions preference in session state
        scan_regions = st.session_state.get("scan_regions")
        if scan_regions is not None:
            region = scan_regions
        # If still None, will auto-discover all enabled regions
        debug_write(f"   - Region: None (auto-discover all enabled regions)")
    elif isinstance(region, str):
        debug_write(f"   - Region: {region} (single region)")
    else:
        debug_write(f"   - Regions: {region} ({len(region)} regions)")
    
    if scans is None or not hasattr(scans, "run_all_scans"):
        st.error("Scans adapter not found: cwt_ui.services.scans.run_all_scans")
        return pd.DataFrame(), pd.DataFrame()
    
    try:
        # Prepare optional session-scoped AWS credential overrides
        creds = None
        if st.session_state.get("aws_override_enabled"):
            debug_write("🔍 **DEBUG:** Using session-scoped credentials")
            auth_method = st.session_state.get("aws_auth_method", "role")
            
            # For role-based auth
            if auth_method == "role":
                rg = st.session_state.get("aws_default_region", "").strip()
                creds = {}
                
                # Add role-specific fields
                role_fields = {
                    "AWS_ROLE_ARN": st.session_state.get("aws_role_arn", "").strip(),
                    "AWS_EXTERNAL_ID": st.session_state.get("aws_external_id", "").strip(),
                    "AWS_ROLE_SESSION_NAME": st.session_state.get("aws_role_session_name", "CloudWasteTracker").strip(),
                    "AWS_DEFAULT_REGION": rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                }
                creds.update({k: v for k, v in role_fields.items() if v})
                debug_write(f"   - Role ARN: {role_fields.get('AWS_ROLE_ARN', 'NOT SET')}")
                debug_write(f"   - External ID: {'SET' if role_fields.get('AWS_EXTERNAL_ID') else 'NOT SET'}")
            else:
                # Legacy IAM User auth (if needed)
                ak = st.session_state.get("aws_access_key_id", "").strip()
                sk = st.session_state.get("aws_secret_access_key", "").strip()
                rg = st.session_state.get("aws_default_region", "").strip()
                stoken = st.session_state.get("aws_session_token", "").strip()
                
                creds = {
                    k: v
                    for k, v in {
                        "AWS_ACCESS_KEY_ID": ak,
                        "AWS_SECRET_ACCESS_KEY": sk,
                        "AWS_DEFAULT_REGION": rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                        "AWS_SESSION_TOKEN": stoken,
                    }.items()
                    if v
                }
            
            debug_write(f"   - Credentials prepared: {list(creds.keys()) if creds else 'NONE'}")
        else:
            debug_write("🔍 **DEBUG:** Using environment credentials")

        debug_write("🔍 **DEBUG:** Calling scans.run_all_scans()...")
        auth_method = st.session_state.get("aws_auth_method", "role")
        debug_write(f"   - Auth method: {auth_method}")
        ec2_df, s3_df = scans.run_all_scans(region=region, aws_credentials=creds, aws_auth_method=auth_method)  # type: ignore
        debug_write("🔍 **DEBUG:** scans.run_all_scans() completed")
        # Stamp scan time
        import datetime as _dt
        scanned_at = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        st.session_state["last_scan_at"] = scanned_at
        debug_write(f"🔍 **DEBUG:** Scan timestamp: {scanned_at}")
        
        def _stamp(df: pd.DataFrame) -> pd.DataFrame:
            if df is None or df.empty:
                return pd.DataFrame()
            out = df.copy()
            out["scanned_at"] = scanned_at
            return out
        
        debug_write("🔍 **DEBUG:** Adding status and timestamp to dataframes...")
        result_ec2 = add_status(_stamp(ec2_df))
        result_s3 = add_status(_stamp(s3_df))
        debug_write(f"🔍 **DEBUG:** Final results - EC2: {result_ec2.shape}, S3: {result_s3.shape}")
        
        return result_ec2, result_s3
    except Exception as e:
        debug_write(f"🔍 **DEBUG:** Scan failed with error: {e}")
        st.warning(f"Live scan failed: {e}")
        return pd.DataFrame(), pd.DataFrame()

# === App ===
st.title("Cloud Waste Tracker 💸")

# DEBUG: Page load indicator
debug_write("🔍 **DEBUG:** Main app.py loaded")

# Session defaults
st.session_state.setdefault("ec2_df", pd.DataFrame())
st.session_state.setdefault("s3_df", pd.DataFrame())
# Don't set a default single region - prefer auto-discovery of all enabled regions
# Users can still specify regions via scan_regions in session state if needed

# AWS credentials session state defaults
st.session_state.setdefault("aws_override_enabled", False)
st.session_state.setdefault("aws_access_key_id", "")
st.session_state.setdefault("aws_secret_access_key", "")
st.session_state.setdefault("aws_default_region", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
st.session_state.setdefault("aws_session_token", "")
st.session_state.setdefault("aws_role_arn", "")
st.session_state.setdefault("aws_external_id", "")
st.session_state.setdefault("aws_role_session_name", "CloudWasteTracker")
st.session_state.setdefault("aws_auth_method", "user")

# DEBUG: Session state check
debug_write("🔍 **DEBUG:** Session state initialized")
debug_write(f"   - Region: {st.session_state.get('region', 'NOT SET')}")
debug_write(f"   - EC2 data: {st.session_state.get('ec2_df', pd.DataFrame()).shape if not st.session_state.get('ec2_df', pd.DataFrame()).empty else 'EMPTY'}")
debug_write(f"   - S3 data: {st.session_state.get('s3_df', pd.DataFrame()).shape if not st.session_state.get('s3_df', pd.DataFrame()).empty else 'EMPTY'}")
debug_write(f"   - Last scan: {st.session_state.get('last_scan_at', 'NEVER')}")

# DEBUG: Credentials check
if st.session_state.get("aws_override_enabled"):
    debug_write("🔍 **DEBUG:** AWS credentials override ENABLED")
    debug_write(f"   - Access Key: {'SET' if st.session_state.get('aws_access_key_id') else 'NOT SET'}")
    debug_write(f"   - Secret Key: {'SET' if st.session_state.get('aws_secret_access_key') else 'NOT SET'}")
    debug_write(f"   - Region: {st.session_state.get('aws_default_region', 'NOT SET')}")
else:
    debug_write("🔍 **DEBUG:** Using environment AWS credentials")

# Optional auto-run is disabled by default to avoid blocking app startup in deployments.
# Enable by setting env CWT_AUTO_SCAN_ON_START=true
auto_scan = os.getenv("CWT_AUTO_SCAN_ON_START", "false").strip().lower() == "true"
if auto_scan and st.session_state["ec2_df"].empty and st.session_state["s3_df"].empty:
    with st.spinner("Running initial live scan across all enabled regions..."):
        # Pass None to auto-discover all enabled regions
        ec2_df, s3_df = run_live_scans(region=None)
        st.session_state["ec2_df"] = ec2_df
        st.session_state["s3_df"]  = s3_df




