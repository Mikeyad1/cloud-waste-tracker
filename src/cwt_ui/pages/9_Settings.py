# src/cwt_ui/pages/9_Settings.py
from __future__ import annotations
from pathlib import Path
import json
import os
import datetime as dt
import streamlit as st
import pandas as pd

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
        st.caption("These fields override environment variables only for this browser session. They are NOT saved to disk.")

        # Initialize session keys
        st.session_state.setdefault("aws_override_enabled", False)
        st.session_state.setdefault("aws_access_key_id", "")
        st.session_state.setdefault("aws_secret_access_key", "")
        st.session_state.setdefault("aws_default_region", os.getenv("AWS_DEFAULT_REGION", data["aws"].get("default_region", "us-east-1")))
        st.session_state.setdefault("aws_session_token", "")

        with st.form("aws_runtime_form", clear_on_submit=False):
            use_override = st.checkbox("Use these credentials for live scans (this session only)", value=st.session_state["aws_override_enabled"])
            ak = st.text_input("AWS_ACCESS_KEY_ID", value=st.session_state.get("aws_access_key_id", ""))
            sk = st.text_input("AWS_SECRET_ACCESS_KEY", value=st.session_state.get("aws_secret_access_key", ""), type="password")
            rg = st.text_input("AWS_DEFAULT_REGION", value=st.session_state.get("aws_default_region", "us-east-1"))
            stoken = st.text_input("AWS_SESSION_TOKEN (optional)", value=st.session_state.get("aws_session_token", ""), type="password")

            submitted = st.form_submit_button("Apply for this Session")
            if submitted:
                # Store only in session_state; do not persist to disk
                st.session_state["aws_override_enabled"] = bool(use_override)
                st.session_state["aws_access_key_id"] = ak.strip()
                st.session_state["aws_secret_access_key"] = sk.strip()
                st.session_state["aws_default_region"] = (rg or os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip()
                st.session_state["aws_session_token"] = stoken.strip()
                st.session_state["region"] = st.session_state["aws_default_region"] or st.session_state.get("region", "us-east-1")
                st.success("Applied to current session. Use the sidebar 'Run Live Scan'.")

        # Optional immediate scan action (uses in-memory credentials)
        def _add_status(df: pd.DataFrame) -> pd.DataFrame:
            if df is None or df.empty:
                return pd.DataFrame()
            out = df.copy()
            if "recommendation" in out.columns and "status" not in out.columns:
                out["status"] = out["recommendation"].astype(str).str.upper().map(
                    lambda x: "🟢 OK" if x == "OK" else "🔴 Action"
                )
            return out

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Run Scan Now"):
                try:
                    # Local import to avoid circulars
                    from cwt_ui.services import scans as _scans
                    creds = None
                    if st.session_state.get("aws_override_enabled"):
                        creds = {
                            k: v for k, v in {
                                "AWS_ACCESS_KEY_ID": st.session_state.get("aws_access_key_id", "").strip(),
                                "AWS_SECRET_ACCESS_KEY": st.session_state.get("aws_secret_access_key", "").strip(),
                                "AWS_DEFAULT_REGION": st.session_state.get("aws_default_region", "").strip(),
                                "AWS_SESSION_TOKEN": st.session_state.get("aws_session_token", "").strip(),
                            }.items() if v
                        }
                    region = st.session_state.get("region") or st.session_state.get("aws_default_region") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                    ec2_df, s3_df = _scans.run_all_scans(region=region, aws_credentials=creds)
                    st.session_state["ec2_df"] = _add_status(ec2_df)
                    st.session_state["s3_df"] = _add_status(s3_df)
                    import datetime as _dt
                    scanned_at = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
                    st.session_state["last_scan_at"] = scanned_at
                    if not st.session_state["ec2_df"].empty:
                        st.session_state["ec2_df"]["scanned_at"] = scanned_at
                    if not st.session_state["s3_df"].empty:
                        st.session_state["s3_df"]["scanned_at"] = scanned_at
                    st.success(f"Live scan completed at {scanned_at} (UTC) with current session credentials.")
                except Exception as e:
                    st.error(f"Scan failed: {e}")

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


# Allow page to render standalone in multipage context (shows only relevant sections)
def _maybe_render_self():
    if st.runtime.exists():  # type: ignore[attr-defined]
        render()


_maybe_render_self()
