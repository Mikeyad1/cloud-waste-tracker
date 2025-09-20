# cwt_ui/pages/9_Settings.py
from __future__ import annotations
from pathlib import Path
import json
import datetime as dt
import streamlit as st

# Where to store settings (next to app.py)
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .../src/cwt_ui/pages -> back to project root
SETTINGS_PATH = PROJECT_ROOT / "settings.json"

DEFAULTS = {
    "email_reports": {
        "enabled": False,
        "recipient": "",
        "schedule": "daily",   # daily | weekly
        "send_time": "09:00",  # HH:MM (local)
        "weekday": "Monday"    # only used if schedule = weekly
    },
    "aws": {
        "default_region": "us-east-1"
    },
    "billing": {
        "currency": "USD"
    },
    "stripe": {
        "public_key": "",
        "secret_key": ""
    },
    "auth": {
        # MVP: demo user list – later will be replaced by Auth0/Clerk
        "demo_users": ["admin@example.com"]
    }
}

def _load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            st.warning(f"Failed reading settings.json, using defaults. Error: {e}")
    return DEFAULTS.copy()

def _save_settings(data: dict) -> bool:
    try:
        # Ensure minimal schema
        merged = DEFAULTS.copy()
        # shallow merge (enough for MVP)
        for k, v in data.items():
            if isinstance(v, dict) and k in merged:
                merged[k].update(v)
            else:
                merged[k] = v
        SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        st.error(f"Failed saving settings.json: {e}")
        return False

def _mask(s: str, keep: int = 4) -> str:
    s = s or ""
    if len(s) <= keep:
        return "•" * len(s)
    return "•" * (len(s) - keep) + s[-keep:]

def render() -> None:
    st.title("Settings ⚙️")
    st.caption(f"Settings file: `{SETTINGS_PATH.name}` (stored at project root)")

    data = _load_settings()

    with st.expander("Email Reports", expanded=True):
        with st.form("email_reports_form"):
            enabled = st.checkbox("Enable daily/weekly report email", value=data["email_reports"].get("enabled", False))
            recipient = st.text_input("Recipient email", value=data["email_reports"].get("recipient", ""))

            schedule = st.selectbox(
                "Schedule",
                options=["daily", "weekly"],
                index=(0 if data["email_reports"].get("schedule", "daily") == "daily" else 1)
            )

            c1, c2 = st.columns(2)
            with c1:
                send_time = st.time_input(
                    "Send time (local)",
                    value=_parse_time(data["email_reports"].get("send_time", "09:00"))
                )
            with c2:
                weekday = st.selectbox(
                    "Weekday (weekly only)",
                    options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                    index=_weekday_index(data["email_reports"].get("weekday", "Monday"))
                )

            submitted = st.form_submit_button("Save Email Settings")
            if submitted:
                data["email_reports"]["enabled"] = enabled
                data["email_reports"]["recipient"] = recipient.strip()
                data["email_reports"]["schedule"] = schedule
                data["email_reports"]["send_time"] = send_time.strftime("%H:%M")
                data["email_reports"]["weekday"] = weekday
                if _save_settings(data):
                    st.success("Email settings saved.")

            st.caption("Tip: actual sending will be added later with a Scheduled Job (Render Cron / APScheduler).")

    with st.expander("AWS Defaults", expanded=True):
        with st.form("aws_form"):
            region = st.text_input(
                "Default AWS region",
                value=data["aws"].get("default_region", "us-east-1")
            )
            currency = st.selectbox(
                "Billing currency (display only)",
                options=["USD", "EUR", "ILS"],
                index=["USD", "EUR", "ILS"].index(data["billing"].get("currency", "USD"))
            )
            submitted = st.form_submit_button("Save AWS Settings")
            if submitted:
                data["aws"]["default_region"] = region.strip() or "us-east-1"
                data["billing"]["currency"] = currency
                if _save_settings(data):
                    st.success("AWS settings saved.")

    with st.expander("Stripe (Payments)", expanded=False):
        with st.form("stripe_form"):
            pk_current = data["stripe"].get("public_key", "")
            sk_current = data["stripe"].get("secret_key", "")

            st.write("Enter your keys from Stripe dashboard (→ Developers → API keys).")
            public_key = st.text_input("Publishable key", value=pk_current)
            secret_key = st.text_input("Secret key", value=sk_current, type="password", help="Will be stored locally in settings.json")

            st.caption(f"Current (masked): pk={_mask(pk_current)}, sk={_mask(sk_current)}")

            submitted = st.form_submit_button("Save Stripe Keys")
            if submitted:
                data["stripe"]["public_key"] = public_key.strip()
                data["stripe"]["secret_key"] = secret_key.strip()
                if _save_settings(data):
                    st.success("Stripe keys saved.")

    with st.expander("Auth (MVP)", expanded=False):
        with st.form("auth_form"):
            st.write("Demo users (MVP only). Later we’ll use Auth0/Clerk.")
            demo = st.text_area(
                "Allowed emails (one per line)",
                value="\n".join(data["auth"].get("demo_users", [])),
                height=120
            )
            submitted = st.form_submit_button("Save Auth List")
            if submitted:
                users = [x.strip() for x in demo.splitlines() if x.strip()]
                data["auth"]["demo_users"] = users
                if _save_settings(data):
                    st.success("Auth demo users saved.")

    st.divider()
    st.subheader("Utilities")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Open settings.json"):
            st.json(data)
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
    # email reports
    if cfg["email_reports"]["enabled"]:
        if not cfg["email_reports"]["recipient"]:
            issues.append("Email reports enabled but recipient is empty.")
        if cfg["email_reports"]["schedule"] not in ("daily","weekly"):
            issues.append("Schedule must be daily/weekly.")
        # time format
        try:
            _ = _parse_time(cfg["email_reports"]["send_time"])
        except Exception:
            issues.append("Invalid send_time in email_reports.")
    # aws
    if not cfg["aws"]["default_region"]:
        issues.append("AWS default_region is empty.")
    # stripe
    if (cfg["stripe"]["public_key"] and not cfg["stripe"]["secret_key"]) or \
       (cfg["stripe"]["secret_key"] and not cfg["stripe"]["public_key"]):
        issues.append("Both Stripe keys should be provided together (or both empty).")
    return issues
