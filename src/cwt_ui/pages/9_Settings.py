# src/cwt_ui/pages/9_Settings.py
from __future__ import annotations
from pathlib import Path
import json
import os
import datetime as dt
import streamlit as st
import pandas as pd

# === Environment detection and debug mode ===
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

# Auto-configure debug mode based on environment
if APP_ENV == "production":
    DEBUG_MODE = False
else:
    DEBUG_MODE = True


# Apply layout fixes inline
st.markdown("""
<style>
    .main .block-container {
        padding-left: 1rem;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Debug utilities inline
def debug_write(message: str):
    """Write debug message only if DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        st.write(message)

# Helper function for adding status column
def _add_status(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "recommendation" in out.columns and "status" not in out.columns:
        out["status"] = out["recommendation"].astype(str).str.upper().map(
            lambda x: "🟢 OK" if x == "OK" else "🔴 Action"
        )
    return out

# -------- storage locations (try project root, else user config dir) --------
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # repo root
USER_CFG_DIR = Path(os.path.expanduser("~")) / ".cloud_waste_tracker"
CANDIDATE_PATHS = [
    PROJECT_ROOT / "settings.json",
    USER_CFG_DIR / "settings.json",
]

def _first_writable(paths: list[Path]) -> Path:
    for p in paths:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            # touch if missing to check writability
            if not p.exists():
                p.write_text("{}", encoding="utf-8")
            # attempt a small write
            p.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            return p
        except Exception:
            continue
    # last resort: in-memory temp under Streamlit runtime
    fallback = Path(st.runtime.temporary_directory()) / "settings.json"  # type: ignore[attr-defined]
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback

SETTINGS_PATH = _first_writable(CANDIDATE_PATHS)

DEFAULTS = {
    "email_reports": {
        "enabled": False,
        "recipient": "",
        "schedule": "daily",   # daily | weekly
        "send_time": "09:00",  # HH:MM (local)
        "weekday": "Monday"
    },
    "aws": {"default_region": "us-east-1"},
    "billing": {"currency": "USD"},
    "stripe": {"public_key": "", "secret_key": ""},
    "auth": {"demo_users": ["admin@example.com"]},
}

# -------- I/O helpers --------
def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)  # type: ignore[index]
        else:
            out[k] = v
    return out

def _load_settings() -> dict:
    try:
        if SETTINGS_PATH.exists():
            return _deep_merge(DEFAULTS, json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
    except Exception as e:
        st.warning(f"Failed reading {SETTINGS_PATH.name}; using defaults. Error: {e}")
    return json.loads(json.dumps(DEFAULTS))  # deep copy

def _save_settings(data: dict) -> bool:
    try:
        merged = _deep_merge(DEFAULTS, data)
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        st.error(f"Failed saving {SETTINGS_PATH.name}: {e}")
        return False

def _mask(s: str, keep: int = 4) -> str:
    s = s or ""
    if len(s) <= keep:
        return "•" * len(s)
    return "•" * (len(s) - keep) + s[-keep:]

# -------- page --------
def render() -> None:
    st.title("Settings ⚙️")
    st.caption(f"Settings file: `{SETTINGS_PATH}`")
    
    # DEBUG: Page load indicator
    debug_write("🔍 **DEBUG:** Settings page loaded")
    debug_write(f"   - Settings path: {SETTINGS_PATH}")

    data = _load_settings()

    with st.expander("Email Reports", expanded=True):
        with st.form("email_reports_form"):
            enabled = st.checkbox("Enable daily/weekly report email", value=data["email_reports"].get("enabled", False))
            recipient = st.text_input("Recipient email", value=data["email_reports"].get("recipient", ""))
            schedule = st.selectbox("Schedule", options=["daily", "weekly"],
                                    index=(0 if data["email_reports"].get("schedule", "daily") == "daily" else 1))
            c1, c2 = st.columns(2)
            with c1:
                send_time = st.time_input("Send time (local)", value=_parse_time(data["email_reports"].get("send_time", "09:00")))
            with c2:
                weekday = st.selectbox(
                    "Weekday (weekly only)",
                    options=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
                    index=_weekday_index(data["email_reports"].get("weekday", "Monday"))
                )
            if st.form_submit_button("Save Email Settings"):
                data["email_reports"] = {
                    "enabled": enabled,
                    "recipient": recipient.strip(),
                    "schedule": schedule,
                    "send_time": send_time.strftime("%H:%M"),
                    "weekday": weekday,
                }
                if _save_settings(data):
                    st.success("Email settings saved.")

        st.caption("Note: sending will be wired later via a scheduler (Render Cron / APScheduler).")

    with st.expander("AWS Defaults", expanded=True):
        with st.form("aws_form"):
            region = st.text_input("Default AWS region", value=data["aws"].get("default_region", "us-east-1"))
            currency = st.selectbox("Billing currency (display only)", options=["USD","EUR","ILS"],
                                    index=["USD","EUR","ILS"].index(data["billing"].get("currency", "USD")))
            if st.form_submit_button("Save AWS Settings"):
                data["aws"]["default_region"] = (region or "us-east-1").strip()
                data["billing"]["currency"] = currency
                if _save_settings(data):
                    # hand off to the running session so the app uses it immediately
                    st.session_state["region"] = data["aws"]["default_region"]
                    st.success("AWS settings saved.")

    # --- In-session AWS credential override (memory only) ---
    with st.expander("AWS Credentials (session only)", expanded=True):
        st.caption("Choose authentication method. These fields override environment variables only for this browser session. They are NOT saved to disk.")

        # Initialize session keys (except aws_auth_method which will be set by the radio widget)
        st.session_state.setdefault("aws_override_enabled", False)
        st.session_state.setdefault("aws_access_key_id", "")
        st.session_state.setdefault("aws_secret_access_key", "")
        st.session_state.setdefault("aws_default_region", os.getenv("AWS_DEFAULT_REGION", data["aws"].get("default_region", "us-east-1")))
        st.session_state.setdefault("aws_session_token", "")
        # Role-specific fields
        st.session_state.setdefault("aws_role_arn", "")
        st.session_state.setdefault("aws_external_id", "")
        st.session_state.setdefault("aws_role_session_name", "CloudWasteTracker")

        # Authentication method selection (outside form for proper reactivity)
        use_override = st.checkbox("Use these credentials for live scans (this session only)", value=st.session_state["aws_override_enabled"])
        
        # Use the session state key directly for immediate updates
        current_auth_method = st.radio(
            "Authentication Method",
            options=["user", "role"],
            format_func=lambda x: "IAM User (Access Key + Secret)" if x == "user" else "IAM Role (AssumeRole + External ID)",
            index=0 if st.session_state.get("aws_auth_method", "user") == "user" else 1,
            horizontal=True,
            key="aws_auth_method"
        )
        
        # Show appropriate fields based on auth method
        if current_auth_method == "user":
            st.info("🔑 **IAM User Credentials** - Provide your AWS Access Key and Secret Key")
            st.warning("⚠️ **Security Note**: These credentials are stored in session memory only and never saved to disk.")
            
            with st.form("aws_user_form", clear_on_submit=False):
                ak = st.text_input("AWS_ACCESS_KEY_ID", value="", placeholder="Enter your AWS Access Key ID", type="password")
                sk = st.text_input("AWS_SECRET_ACCESS_KEY", value="", placeholder="Enter your AWS Secret Access Key", type="password")
                stoken = st.text_input("AWS_SESSION_TOKEN (optional)", value="", placeholder="Optional: For temporary credentials", type="password", 
                                     help="Optional: For temporary credentials")
                rg = st.text_input("AWS_DEFAULT_REGION", value="us-east-1", placeholder="us-east-1")
                
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("Apply for this Session")
                    if submitted:
                        # Store only in session_state; do not persist to disk
                        st.session_state["aws_override_enabled"] = bool(use_override)
                        # Note: aws_auth_method is managed by the radio widget, don't set it here
                        st.session_state["aws_access_key_id"] = ak.strip()
                        st.session_state["aws_secret_access_key"] = sk.strip()
                        st.session_state["aws_default_region"] = (rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip()
                        st.session_state["aws_session_token"] = stoken.strip()
                        
                        # Clear role fields when using user auth
                        st.session_state["aws_role_arn"] = ""
                        st.session_state["aws_external_id"] = ""
                        st.session_state["aws_role_session_name"] = "CloudWasteTracker"
                        
                        st.session_state["region"] = st.session_state["aws_default_region"] or st.session_state.get("region", "us-east-1")
                        st.success("Applied to current session. Use the sidebar 'Run Live Scan'.")
                
                with col2:
                    # Test scan button - check if credentials are filled
                    has_creds = bool(ak.strip() and sk.strip())
                    test_scan = st.form_submit_button("🚀 Test Scan", disabled=not has_creds,
                                                   help="Test scan with current credentials" if has_creds else "Enter credentials to enable")
                    
                    if test_scan and has_creds:
                        try:
                            from cwt_ui.services import scans as _scans
                            
                            # Prepare credentials
                            creds = {
                                "AWS_ACCESS_KEY_ID": ak.strip(),
                                "AWS_SECRET_ACCESS_KEY": sk.strip(),
                                "AWS_DEFAULT_REGION": (rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip(),
                                "AWS_SESSION_TOKEN": stoken.strip(),
                            }
                            
                            region = st.session_state.get("region") or rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                            ec2_df, s3_df = _scans.run_all_scans(region=region, aws_credentials=creds, aws_auth_method="user")
                            
                            st.session_state["ec2_df"] = _add_status(ec2_df)
                            st.session_state["s3_df"] = _add_status(s3_df)
                            
                            # Generate timestamp in Israel time
                            import datetime as _dt
                            from datetime import timedelta
                            israel_time = _dt.datetime.utcnow() + timedelta(hours=3)
                            scanned_at = israel_time.replace(microsecond=0).isoformat() + " (Israel Time)"
                            st.session_state["last_scan_at"] = scanned_at
                            
                            # Save to database
                            try:
                                from db.repo import save_scan_results
                                save_scan_results(ec2_df, s3_df, scanned_at)
                                debug_write("🔍 **DEBUG:** Scan results saved to database")
                            except Exception as e:
                                debug_write(f"🔍 **DEBUG:** Failed to save to database: {e}")
                            
                            if not st.session_state["ec2_df"].empty:
                                st.session_state["ec2_df"]["scanned_at"] = scanned_at
                            if not st.session_state["s3_df"].empty:
                                st.session_state["s3_df"]["scanned_at"] = scanned_at
                            
                            st.success(f"✅ Test scan completed at {scanned_at} using IAM User credentials.")
                            
                        except Exception as e:
                            st.error(f"Test scan failed: {e}")
        
        else:
            st.info("🔒 **IAM Role Credentials** - More secure, uses temporary credentials via AssumeRole")
            
            with st.expander("📋 How to set up IAM Role authentication", expanded=False):
                st.markdown("""
                **1. Create an IAM Role:**
                - Go to AWS IAM Console → Roles → Create Role
                - Choose "AWS Account" → "Another AWS Account"
                - Enter your account ID or use "Any" for cross-account access
                - Attach policies: `AmazonEC2ReadOnlyAccess`, `AmazonS3ReadOnlyAccess`, `CostExplorerReadOnlyAccess`
                
                **2. Set up Trust Policy:**
                ```json
                {
                  "Version": "2012-10-17",
                  "Statement": [
                    {
                      "Effect": "Allow",
                      "Principal": {
                        "AWS": "arn:aws:iam::YOUR-ACCOUNT-ID:user/YOUR-USER"
                      },
                      "Action": "sts:AssumeRole",
                      "Condition": {
                        "StringEquals": {
                          "sts:ExternalId": "your-external-id"
                        }
                      }
                    }
                  ]
                }
                ```
                
                **3. Use the Role ARN:**
                - Copy the Role ARN from the role details page
                - Enter it in the "Role ARN" field below
                """)
            
            with st.form("aws_role_form", clear_on_submit=False):
                role_arn = st.text_input("Role ARN", value="", placeholder="arn:aws:iam::123456789012:role/CloudWasteTrackerRole",
                                       help="ARN of the IAM role to assume (e.g., arn:aws:iam::123456789012:role/CloudWasteTrackerRole)")
                external_id = st.text_input("External ID", value="", placeholder="Optional external ID for security",
                                          help="External ID for additional security (optional but recommended)")
                session_name = st.text_input("Session Name", value="CloudWasteTracker", placeholder="CloudWasteTracker",
                                           help="Name for this session (will appear in CloudTrail)")
                rg = st.text_input("AWS_DEFAULT_REGION", value="us-east-1", placeholder="us-east-1")
                
                # Check if base credentials are available
                env_ak = os.getenv("AWS_ACCESS_KEY_ID")
                env_sk = os.getenv("AWS_SECRET_ACCESS_KEY")
                
                # Always use environment credentials if available, otherwise show manual input
                if env_ak and env_sk and env_ak.strip() and env_sk.strip():
                    st.success("✅ **Base credentials detected** from environment variables")
                    st.caption("Using AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from environment")
                    st.warning("⚠️ **Security Note**: Base credentials are loaded from environment variables, not displayed here for security.")
                    # Use environment credentials (not displayed)
                    ak = env_ak.strip()
                    sk = env_sk.strip()
                else:
                    st.warning("⚠️ **No base credentials found** in environment variables")
                    st.caption("Base credentials are required to assume the role")
                    ak = st.text_input("Base AWS_ACCESS_KEY_ID", value="", placeholder="Enter base access key", type="password",
                                     help="Access key of user/service that can assume the role")
                    sk = st.text_input("Base AWS_SECRET_ACCESS_KEY", value="", placeholder="Enter base secret key", type="password",
                                     help="Secret key of user/service that can assume the role")
                
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("Apply for this Session")
                    if submitted:
                        # Store only in session_state; do not persist to disk
                        st.session_state["aws_override_enabled"] = bool(use_override)
                        # Note: aws_auth_method is managed by the radio widget, don't set it here
                        st.session_state["aws_access_key_id"] = ak.strip()
                        st.session_state["aws_secret_access_key"] = sk.strip()
                        st.session_state["aws_default_region"] = (rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip()
                        st.session_state["aws_session_token"] = ""  # Role generates its own
                        
                        # Store role-specific fields
                        st.session_state["aws_role_arn"] = role_arn.strip()
                        st.session_state["aws_external_id"] = external_id.strip()
                        st.session_state["aws_role_session_name"] = session_name.strip()
                        
                        st.session_state["region"] = st.session_state["aws_default_region"] or st.session_state.get("region", "us-east-1")
                        
                        # Show confirmation message
                        if env_ak and env_sk:
                            st.success("✅ Applied role configuration with environment base credentials. Use the sidebar 'Run Live Scan'.")
                        else:
                            st.success("✅ Applied role configuration with manual base credentials. Use the sidebar 'Run Live Scan'.")
                
                with col2:
                    # Test scan button for role - check if required fields are filled
                    has_role_creds = bool(role_arn.strip() and ak and sk)
                    test_scan = st.form_submit_button("🚀 Test Scan", disabled=not has_role_creds,
                                                   help="Test role assumption and scan" if has_role_creds else "Enter role ARN and base credentials to enable")
                    
                    if test_scan and has_role_creds:
                        try:
                            from cwt_ui.services import scans as _scans
                            
                            # Prepare credentials for role assumption
                            debug_write(f"🔍 **DEBUG:** IAM Role test scan - using environment credentials naturally")
                            debug_write(f"🔍 **DEBUG:** Role ARN: {role_arn.strip()}")
                            debug_write(f"🔍 **DEBUG:** External ID: {'SET' if external_id.strip() else 'NOT SET'}")
                            
                            # Store role configuration in session state for this test
                            st.session_state["aws_role_arn"] = role_arn.strip()
                            st.session_state["aws_external_id"] = external_id.strip()
                            st.session_state["aws_role_session_name"] = session_name.strip()
                            
                            region = st.session_state.get("region") or rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                            
                            # Use the same scan approach as Dashboard - scans service will read from session state
                            ec2_df, s3_df = _scans.run_all_scans(region=region, aws_credentials=None, aws_auth_method="role")
                            
                            st.session_state["ec2_df"] = _add_status(ec2_df)
                            st.session_state["s3_df"] = _add_status(s3_df)
                            
                            # Generate timestamp in Israel time
                            import datetime as _dt
                            from datetime import timedelta
                            israel_time = _dt.datetime.utcnow() + timedelta(hours=3)
                            scanned_at = israel_time.replace(microsecond=0).isoformat() + " (Israel Time)"
                            st.session_state["last_scan_at"] = scanned_at
                            
                            # Save to database
                            try:
                                from db.repo import save_scan_results
                                save_scan_results(ec2_df, s3_df, scanned_at)
                                debug_write("🔍 **DEBUG:** Role scan results saved to database")
                            except Exception as e:
                                debug_write(f"🔍 **DEBUG:** Failed to save role scan to database: {e}")
                            
                            if not st.session_state["ec2_df"].empty:
                                st.session_state["ec2_df"]["scanned_at"] = scanned_at
                            if not st.session_state["s3_df"].empty:
                                st.session_state["s3_df"]["scanned_at"] = scanned_at
                            
                            st.success(f"✅ Test scan completed at {scanned_at} using IAM Role (AssumeRole) credentials.")
                            
                        except Exception as e:
                            st.error(f"Test scan failed: {e}")


        st.info("💡 **Tip:** Use the 'Test Scan' button within each form to verify your credentials work correctly.")
        
        # Clear session state button for debugging
        if st.button("🗑️ Clear All Session Data", help="Clear all stored credentials and session data"):
            keys_to_clear = [
                "aws_access_key_id", "aws_secret_access_key", "aws_default_region", 
                "aws_session_token", "aws_role_arn", "aws_external_id", 
                "aws_role_session_name", "aws_auth_method", "aws_override_enabled",
                "ec2_df", "s3_df", "last_scan_at"
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("Session data cleared! Please reconfigure your credentials.")
            st.rerun()

    with st.expander("Stripe (Payments)", expanded=False):
        with st.form("stripe_form"):
            pk_current = data["stripe"].get("public_key", "")
            sk_current = data["stripe"].get("secret_key", "")
            st.write("Enter your Stripe keys (Developers → API keys). For production, prefer environment variables.")
            public_key = st.text_input("Publishable key", value=pk_current)
            secret_key = st.text_input("Secret key", value=sk_current, type="password",
                                       help="For production deployments, store this in environment variables.")
            st.caption(f"Current (masked): pk={_mask(pk_current)}, sk={_mask(sk_current)}")
            if st.form_submit_button("Save Stripe Keys"):
                data["stripe"]["public_key"] = public_key.strip()
                data["stripe"]["secret_key"] = secret_key.strip()
                if _save_settings(data):
                    st.success("Stripe keys saved.")

    with st.expander("Auth (MVP)", expanded=False):
        with st.form("auth_form"):
            st.write("Demo users (MVP only). Will be replaced by a real auth provider later.")
            demo = st.text_area("Allowed emails (one per line)",
                                value="\n".join(data["auth"].get("demo_users", [])),
                                height=120)
            if st.form_submit_button("Save Auth List"):
                users = [x.strip() for x in demo.splitlines() if x.strip()]
                data["auth"]["demo_users"] = users
                if _save_settings(data):
                    st.success("Auth demo users saved.")

    st.divider()
    st.subheader("Utilities")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Open settings.json"):
            st.json(_load_settings())
    with c2:
        if st.button("Reset to defaults"):
            if _save_settings(DEFAULTS):
                st.success("Reset done. Reload the page.")
    with c3:
        if st.button("Validate config"):
            errs = _validate(data)
            if errs:
                st.error("Found issues:\n- " + "\n- ".join(errs))
            else:
                st.success("Config looks good ✅")

# -------- helpers --------
def _weekday_index(name: str) -> int:
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    try:
        return days.index(name)
    except ValueError:
        return 0

def _parse_time(hhmm: str) -> dt.time:
    try:
        h, m = (int(x) for x in hhmm.split(":"))
        return dt.time(hour=h, minute=m)
    except Exception:
        return dt.time(hour=9, minute=0)

def _validate(cfg: dict) -> list[str]:
    issues: list[str] = []
    if cfg.get("email_reports", {}).get("enabled"):
        if not cfg["email_reports"].get("recipient"):
            issues.append("Email reports enabled but recipient is empty.")
        if cfg["email_reports"].get("schedule") not in ("daily","weekly"):
            issues.append("Schedule must be daily/weekly.")
        try:
            _ = _parse_time(cfg["email_reports"].get("send_time", "09:00"))
        except Exception:
            issues.append("Invalid send_time in email_reports.")
    if not cfg.get("aws", {}).get("default_region"):
        issues.append("AWS default_region is empty.")
    if (cfg.get("stripe", {}).get("public_key") and not cfg["stripe"].get("secret_key")) or \
       (cfg.get("stripe", {}).get("secret_key") and not cfg["stripe"].get("public_key")):
        issues.append("Both Stripe keys should be provided together (or both empty).")
    return issues


def _load() -> dict:
    """Load settings from disk."""
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        debug_write(f"⚠️ Failed to load settings: {e}")
    return {}

def _save(cfg: dict) -> None:
    """Save settings to disk."""
    try:
        SETTINGS_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as e:
        debug_write(f"⚠️ Failed to save settings: {e}")

def _add_status(df: pd.DataFrame) -> pd.DataFrame:
    """Add status column to dataframe if it doesn't exist."""
    if df.empty:
        return df
    if "status" not in df.columns:
        df["status"] = "active"
    return df

def render():
    """Main settings page render function."""
    debug_write("🔍 **DEBUG:** Settings page rendering")
    
    st.markdown("""
    <style>
        .main .block-container {
            padding-left: 1rem;
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("⚙️ Settings")
    
    # Load current settings
    cfg = _load()
    
    # AWS Credentials Override Section
    st.header("🔐 AWS Credentials")
    st.markdown("Override AWS credentials for live scans (session-only, not saved to disk).")
    
    # Authentication method selection (outside form for proper reactivity)
    use_override = st.checkbox("Use these credentials for live scans (this session only)", value=st.session_state.get("aws_override_enabled", False))
    
    current_auth_method = st.radio(
        "Authentication Method",
        options=["user", "role"],
        format_func=lambda x: "IAM User (Access Key + Secret)" if x == "user" else "IAM Role (AssumeRole + External ID)",
        index=0 if st.session_state.get("aws_auth_method", "user") == "user" else 1,
        horizontal=True,
        key="aws_auth_method"
    )
    
    # Show appropriate fields based on auth method
    if current_auth_method == "user":
        st.info("🔑 **IAM User Credentials** - Provide your AWS Access Key and Secret Key")
        st.warning("⚠️ **Security Note**: These credentials are stored in session memory only and never saved to disk.")
        
        with st.form("aws_user_form", clear_on_submit=False):
            ak = st.text_input("AWS_ACCESS_KEY_ID", value="", placeholder="Enter your AWS Access Key ID", type="password")
            sk = st.text_input("AWS_SECRET_ACCESS_KEY", value="", placeholder="Enter your AWS Secret Access Key", type="password")
            stoken = st.text_input("AWS_SESSION_TOKEN (optional)", value="", placeholder="Optional: For temporary credentials", type="password", 
                                 help="Optional: For temporary credentials")
            rg = st.text_input("AWS_DEFAULT_REGION", value="us-east-1", placeholder="us-east-1")
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Apply for this Session")
                if submitted:
                    st.session_state["aws_override_enabled"] = bool(use_override)
                    st.session_state["aws_access_key_id"] = ak.strip()
                    st.session_state["aws_secret_access_key"] = sk.strip()
                    st.session_state["aws_default_region"] = (rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip()
                    st.session_state["aws_session_token"] = stoken.strip()
                    
                    st.session_state["aws_role_arn"] = ""
                    st.session_state["aws_external_id"] = ""
                    st.session_state["aws_role_session_name"] = "CloudWasteTracker"
                    
                    st.session_state["region"] = st.session_state["aws_default_region"] or st.session_state.get("region", "us-east-1")
                    st.success("Applied to current session. Use the sidebar 'Run Live Scan'.")
            
            with col2:
                has_creds = bool(ak.strip() and sk.strip())
                test_scan = st.form_submit_button("🚀 Test Scan", disabled=not has_creds,
                                               help="Test scan with current credentials" if has_creds else "Enter credentials to enable")
                
                if test_scan and has_creds:
                    try:
                        from cwt_ui.services import scans as _scans
                        
                        creds = {
                            "AWS_ACCESS_KEY_ID": ak.strip(),
                            "AWS_SECRET_ACCESS_KEY": sk.strip(),
                            "AWS_DEFAULT_REGION": (rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip(),
                            "AWS_SESSION_TOKEN": stoken.strip(),
                        }
                        
                        region = st.session_state.get("region") or rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                        ec2_df, s3_df = _scans.run_all_scans(region=region, aws_credentials=creds, aws_auth_method="user")
                        
                        st.session_state["ec2_df"] = _add_status(ec2_df)
                        st.session_state["s3_df"] = _add_status(s3_df)
                        
                        # Generate timestamp in Israel time
                        import datetime as _dt
                        from datetime import timedelta
                        israel_time = _dt.datetime.utcnow() + timedelta(hours=3)
                        scanned_at = israel_time.replace(microsecond=0).isoformat() + " (Israel Time)"
                        st.session_state["last_scan_at"] = scanned_at
                        
                        # Save to database
                        try:
                            from db.repo import save_scan_results
                            save_scan_results(ec2_df, s3_df, scanned_at)
                            debug_write("🔍 **DEBUG:** User scan results saved to database")
                        except Exception as e:
                            debug_write(f"🔍 **DEBUG:** Failed to save user scan to database: {e}")
                        
                        if not st.session_state["ec2_df"].empty:
                            st.session_state["ec2_df"]["scanned_at"] = scanned_at
                        if not st.session_state["s3_df"].empty:
                            st.session_state["s3_df"]["scanned_at"] = scanned_at
                        
                        st.success(f"✅ Test scan completed at {scanned_at} using IAM User credentials.")
                        
                    except Exception as e:
                        st.error(f"Test scan failed: {e}")
    
    else: # current_auth_method == "role"
        st.info("🔒 **IAM Role Credentials** - More secure, uses temporary credentials via AssumeRole")
        
        with st.expander("📋 How to set up IAM Role authentication", expanded=False):
            st.markdown("""
            **1. Create an IAM Role:**
            - Go to AWS IAM Console → Roles → Create Role
            - Choose "AWS Account" → "Another AWS Account"
            - Enter your account ID or use "Any" for cross-account access
            - Attach policies: `AmazonEC2ReadOnlyAccess`, `AmazonS3ReadOnlyAccess`, `CostExplorerReadOnlyAccess`
            
            **2. Set up Trust Policy:**
            ```json
            {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Principal": {
                    "AWS": "arn:aws:iam::YOUR-ACCOUNT-ID:user/YOUR-USER"
                  },
                  "Action": "sts:AssumeRole",
                  "Condition": {
                    "StringEquals": {
                      "sts:ExternalId": "your-external-id"
                    }
                  }
                }
              ]
            }
            ```
            
            **3. Use the Role ARN:**
            - Copy the Role ARN from the role details page
            - Enter it in the "Role ARN" field below
            """)
        
        with st.form("aws_role_form", clear_on_submit=False):
            role_arn = st.text_input("Role ARN", value="", placeholder="arn:aws:iam::123456789012:role/CloudWasteTrackerRole",
                                   help="ARN of the IAM role to assume (e.g., arn:aws:iam::123456789012:role/CloudWasteTrackerRole)")
            external_id = st.text_input("External ID", value="", placeholder="Optional external ID for security",
                                      help="External ID for additional security (optional but recommended)")
            session_name = st.text_input("Session Name", value="CloudWasteTracker", placeholder="CloudWasteTracker",
                                       help="Name for this session (will appear in CloudTrail)")
            rg = st.text_input("AWS_DEFAULT_REGION", value="us-east-1", placeholder="us-east-1")
            
            # Check if base credentials are available
            env_ak = os.getenv("AWS_ACCESS_KEY_ID")
            env_sk = os.getenv("AWS_SECRET_ACCESS_KEY")
            
            # Always use environment credentials if available, otherwise show manual input
            if env_ak and env_sk and env_ak.strip() and env_sk.strip():
                st.success("✅ **Base credentials detected** from environment variables")
                st.caption("Using AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from environment")
                st.warning("⚠️ **Security Note**: Base credentials are loaded from environment variables, not displayed here for security.")
                # Use environment credentials (not displayed)
                ak = env_ak.strip()
                sk = env_sk.strip()
            else:
                st.warning("⚠️ **No base credentials found** in environment variables")
                st.caption("Base credentials are required to assume the role")
                ak = st.text_input("Base AWS_ACCESS_KEY_ID", value="", placeholder="Enter base access key", type="password",
                                 help="Access key of user/service that can assume the role")
                sk = st.text_input("Base AWS_SECRET_ACCESS_KEY", value="", placeholder="Enter base secret key", type="password",
                                 help="Secret key of user/service that can assume the role")
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Apply for this Session")
                if submitted:
                    st.session_state["aws_override_enabled"] = bool(use_override)
                    st.session_state["aws_access_key_id"] = ak.strip()
                    st.session_state["aws_secret_access_key"] = sk.strip()
                    st.session_state["aws_default_region"] = (rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip()
                    st.session_state["aws_session_token"] = ""  # Role generates its own
                    
                    st.session_state["aws_role_arn"] = role_arn.strip()
                    st.session_state["aws_external_id"] = external_id.strip()
                    st.session_state["aws_role_session_name"] = session_name.strip()
                    
                    st.session_state["region"] = st.session_state["aws_default_region"] or st.session_state.get("region", "us-east-1")
                    
                    if env_ak and env_sk:
                        st.success("✅ Applied role configuration with environment base credentials. Use the sidebar 'Run Live Scan'.")
                    else:
                        st.success("✅ Applied role configuration with manual base credentials. Use the sidebar 'Run Live Scan'.")
            
            with col2:
                has_role_creds = bool(role_arn.strip() and ak and sk)
                test_scan = st.form_submit_button("🚀 Test Scan", disabled=not has_role_creds,
                                               help="Test role assumption and scan" if has_role_creds else "Enter role ARN and base credentials to enable")
                
                if test_scan and has_role_creds:
                    try:
                        from cwt_ui.services import scans as _scans
                        
                        # Prepare credentials for role assumption
                        debug_write(f"🔍 **DEBUG:** IAM Role test scan - using environment credentials naturally")
                        debug_write(f"🔍 **DEBUG:** Role ARN: {role_arn.strip()}")
                        debug_write(f"🔍 **DEBUG:** External ID: {'SET' if external_id.strip() else 'NOT SET'}")
                        
                        # Store role configuration in session state for this test
                        st.session_state["aws_role_arn"] = role_arn.strip()
                        st.session_state["aws_external_id"] = external_id.strip()
                        st.session_state["aws_role_session_name"] = session_name.strip()
                        
                        region = st.session_state.get("region") or rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                        
                        # Use the same scan approach as Dashboard - scans service will read from session state
                        ec2_df, s3_df = _scans.run_all_scans(region=region, aws_credentials=None, aws_auth_method="role")
                        
                        st.session_state["ec2_df"] = _add_status(ec2_df)
                        st.session_state["s3_df"] = _add_status(s3_df)
                        
                        # Generate timestamp in Israel time
                        import datetime as _dt
                        from datetime import timedelta
                        israel_time = _dt.datetime.utcnow() + timedelta(hours=3)
                        scanned_at = israel_time.replace(microsecond=0).isoformat() + " (Israel Time)"
                        st.session_state["last_scan_at"] = scanned_at
                        
                        # Save to database
                        try:
                            from db.repo import save_scan_results
                            save_scan_results(ec2_df, s3_df, scanned_at)
                            debug_write("🔍 **DEBUG:** Final role scan results saved to database")
                        except Exception as e:
                            debug_write(f"🔍 **DEBUG:** Failed to save final role scan to database: {e}")
                        
                        if not st.session_state["ec2_df"].empty:
                            st.session_state["ec2_df"]["scanned_at"] = scanned_at
                        if not st.session_state["s3_df"].empty:
                            st.session_state["s3_df"]["scanned_at"] = scanned_at
                        
                        st.success(f"✅ Test scan completed at {scanned_at} using IAM Role (AssumeRole) credentials.")
                        
                    except Exception as e:
                        st.error(f"Test scan failed: {e}")
    
    # Clear session data button for debugging
    if st.button("🗑️ Clear All Session Data", help="Clear all cached credentials and scan data"):
        keys_to_clear = [
            "aws_override_enabled", "aws_access_key_id", "aws_secret_access_key", 
            "aws_default_region", "aws_session_token", "aws_role_arn", 
            "aws_external_id", "aws_role_session_name", "aws_auth_method",
            "ec2_df", "s3_df", "last_scan_at", "region"
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.success("✅ All session data cleared")
        st.rerun()

# Allow page to render standalone in multipage context (shows only relevant sections)
def _maybe_render_self():
    if st.runtime.exists():  # type: ignore[attr-defined]
        debug_write("🔍 **DEBUG:** Settings self-render called")
        render()


_maybe_render_self()
