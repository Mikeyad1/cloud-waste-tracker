# src/cwt_ui/pages/1_Dashboard.py
from __future__ import annotations
import pandas as pd
import streamlit as st
import os

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

def _compute_summary(ec2_df: pd.DataFrame, s3_df: pd.DataFrame):
    """Return (idle_count, monthly_waste, cold_gb) from the given frames, robust to missing columns."""
    idle_count = 0
    monthly_waste = 0.0
    cold_gb = 0.0

    if ec2_df is not None and not ec2_df.empty:
        if "recommendation" in ec2_df.columns:
            mask = ~ec2_df["recommendation"].astype(str).str.upper().eq("OK")
        else:
            # If the scanner didn’t provide a recommendation column, treat all rows as actionable.
            mask = pd.Series(True, index=ec2_df.index)

        idle_count = int(mask.sum())

        if "monthly_cost_usd" in ec2_df.columns:
            monthly_waste = pd.to_numeric(
                ec2_df.loc[mask, "monthly_cost_usd"], errors="coerce"
            ).fillna(0.0).sum()

    if s3_df is not None and not s3_df.empty and "standard_cold_gb" in s3_df.columns:
        cold_gb = pd.to_numeric(s3_df["standard_cold_gb"], errors="coerce").fillna(0.0).sum()

    return int(idle_count), float(monthly_waste), float(cold_gb)


def _prepare_ec2_table(ec2_df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned EC2 table for display."""
    if ec2_df is None or ec2_df.empty:
        return pd.DataFrame()
    cols = [
        "status", "instance_id", "name", "instance_type",
        "region", "avg_cpu_7d", "monthly_cost_usd", "recommendation"
    ]
    cols = [c for c in cols if c in ec2_df.columns]
    df = ec2_df[cols].copy()

    if "monthly_cost_usd" in df.columns:
        df["monthly_cost_usd"] = pd.to_numeric(df["monthly_cost_usd"], errors="coerce").fillna(0.0)
        df = df.sort_values("monthly_cost_usd", ascending=False)

    if "avg_cpu_7d" in df.columns:
        df["avg_cpu_7d"] = pd.to_numeric(df["avg_cpu_7d"], errors="coerce").fillna(0.0)

    # Rename for clarity
    rename_map = {
        "instance_id": "Instance ID",
        "name": "Name",
        "instance_type": "Instance Type",
        "region": "Region",
        "avg_cpu_7d": "Avg CPU (7d)",
        "monthly_cost_usd": "Monthly Cost ($)",
        "recommendation": "Recommendation",
        "status": "Status",
        "scanned_at": "Scanned At",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


def _prepare_s3_table(s3_df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned S3 table for display."""
    if s3_df is None or s3_df.empty:
        return pd.DataFrame()
    cols = [
        "status", "bucket", "region",
        "size_total_gb", "objects_total",
        "standard_cold_gb", "standard_cold_objects",
        "lifecycle_defined", "recommendation", "notes"
    ]
    cols = [c for c in cols if c in s3_df.columns]
    df = s3_df[cols].copy()

    for c in ("size_total_gb", "standard_cold_gb"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    for c in ("objects_total", "standard_cold_objects"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    rename_map = {
        "bucket": "Bucket",
        "region": "Region",
        "size_total_gb": "Total Size (GB)",
        "objects_total": "Objects",
        "standard_cold_gb": "Cold STANDARD (GB)",
        "standard_cold_objects": "Cold STANDARD (Objects)",
        "lifecycle_defined": "Lifecycle Config",
        "recommendation": "Recommendation",
        "notes": "Why",
        "status": "Status",
        "scanned_at": "Scanned At",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


def render(ec2_df: pd.DataFrame, s3_df: pd.DataFrame, cards, tables, formatters) -> None:
    """
    Dashboard:
    - 3 KPIs
    - EC2 table (Top by monthly cost)
    - S3 Summary table
    """
    import streamlit as st
    
    # DEBUG: Page load indicator
    debug_write("🔍 **DEBUG:** Dashboard page loaded")
    debug_write(f"   - EC2 data shape: {ec2_df.shape if not ec2_df.empty else 'EMPTY'}")
    debug_write(f"   - S3 data shape: {s3_df.shape if not s3_df.empty else 'EMPTY'}")
    if not ec2_df.empty:
        debug_write(f"   - EC2 columns: {list(ec2_df.columns)}")
    if not s3_df.empty:
        debug_write(f"   - S3 columns: {list(s3_df.columns)}")

    # Scan Controls Section
    with st.container():
        st.subheader("🔍 Scan Controls")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            region = st.text_input(
                "AWS Region",
                value=st.session_state.get("region", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
                help="Region to scan for resources",
                key="dashboard_region"
            )
            st.session_state["region"] = region
        
        with col2:
            if st.button("🔄 Refresh from Database", type="primary", use_container_width=True):
                try:
                    # Import database function
                    from db.repo import get_last_scan
                    
                    debug_write("🔍 **DEBUG:** Dashboard refresh button clicked - loading from database...")
                    
                    # Load last scan from database
                    ec2_df, s3_df, scanned_at = get_last_scan()
                    debug_write("🔍 **DEBUG:** Database load completed")
                    debug_write(f"   - EC2 results: {ec2_df.shape if not ec2_df.empty else 'EMPTY'}")
                    debug_write(f"   - S3 results: {s3_df.shape if not s3_df.empty else 'EMPTY'}")
                    debug_write(f"   - Scan timestamp: {scanned_at}")
                    
                    # Update session state with results
                    st.session_state["ec2_df"] = ec2_df
                    st.session_state["s3_df"] = s3_df
                    st.session_state["last_scan_at"] = scanned_at
                    
                    # Add timestamp to dataframes for display
                    if not ec2_df.empty:
                        ec2_df["scanned_at"] = scanned_at
                        st.session_state["ec2_df"] = ec2_df
                    if not s3_df.empty:
                        s3_df["scanned_at"] = scanned_at
                        st.session_state["s3_df"] = s3_df
                    
                    if scanned_at:
                        st.success(f"✅ Data refreshed from database (scanned at {scanned_at})")
                    else:
                        st.info("ℹ️ No scan data found in database. Run the worker to populate data.")
                    st.rerun()  # Refresh the page to show new data
                    
                except Exception as e:
                    debug_write(f"🔍 **DEBUG:** Database refresh failed with error: {e}")
                    st.error(f"Failed to load data from database: {e}")
        
        st.caption(f"Last scan: {st.session_state.get('last_scan_at', 'Never')}")
        st.divider()

    # KPIs
    idle_count, monthly_waste, cold_gb = _compute_summary(ec2_df, s3_df)
    # Estimated potential savings: sum of monthly cost for actionable EC2 rows
    potential_savings = 0.0
    if ec2_df is not None and not ec2_df.empty:
        mask = ~ec2_df.get("recommendation", pd.Series(index=ec2_df.index, dtype=str)).astype(str).str.upper().eq("OK")
        if "monthly_cost_usd" in ec2_df.columns:
            potential_savings = pd.to_numeric(ec2_df.loc[mask, "monthly_cost_usd"], errors="coerce").fillna(0.0).sum()
    last_scan = st.session_state.get("last_scan_at")
    # Cost Explorer summaries (if permissions available)
    spend_7d = None
    spend_mtd = None
    credits_remaining = None
    try:
        from cwt_ui.services.scans import get_cost_explorer_client, fetch_spend_summary, fetch_credit_balance
        ce = get_cost_explorer_client()
        sums = fetch_spend_summary(ce)
        spend_7d = sums.get("last_7_days")
        spend_mtd = sums.get("month_to_date")
        credits_remaining = fetch_credit_balance(ce)
    except Exception:
        pass
    c1, c2, c3 = st.columns(3)
    with c1:
        cards.metric("Idle EC2 (est.)", str(idle_count), "instances needing action")
    with c2:
        cards.metric("Est. Monthly Waste", formatters.currency(monthly_waste))
    with c3:
        cards.metric("S3 Cold GB", f"{cold_gb:,.2f}")
    c4, c5, c6 = st.columns(3)
    with c4:
        cards.metric("Potential Savings (est.)", formatters.currency(potential_savings))
    with c5:
        cards.metric("Spend: Last 7d", formatters.currency(spend_7d) if spend_7d is not None else "N/A")
    with c6:
        cards.metric("Spend: Month-to-Date", formatters.currency(spend_mtd) if spend_mtd is not None else "N/A")
    st.caption(f"Last Scan: {last_scan or '-'} | Credits: {formatters.currency(credits_remaining) if credits_remaining is not None else 'N/A'}")

    # EC2
    st.subheader("EC2 – Top by Monthly Cost")
    ec2_tbl = _prepare_ec2_table(ec2_df)
    if ec2_tbl.empty:
        st.info("No EC2 data.")
    else:
        tables.render(
            ec2_tbl,
            column_order=[c for c in [
                "Status","Instance ID","Name","Instance Type","Region","Avg CPU (7d)","Monthly Cost ($)","Recommendation","Scanned At"
            ] if c in ec2_tbl.columns],
            numeric_formatters={
                "Monthly Cost ($)": formatters.currency,
                "Avg CPU (7d)": lambda x: f"{float(x):.2f}",
            },
            highlight_rules={"Status": _status_badge},
        )

    st.divider()

    # S3
    st.subheader("S3 Buckets Summary")
    s3_tbl = _prepare_s3_table(s3_df)
    if s3_tbl.empty:
        st.info("No S3 data.")
    else:
        tables.render(
            s3_tbl,
            column_order=[c for c in [
                "Status","Bucket","Region","Total Size (GB)","Objects","Cold STANDARD (GB)","Cold STANDARD (Objects)","Lifecycle Config","Recommendation","Why","Scanned At"
            ] if c in s3_tbl.columns],
            numeric_formatters={
                "Total Size (GB)": lambda x: formatters.human_gb(x, 2),
                "Cold STANDARD (GB)": lambda x: formatters.human_gb(x, 2),
                "Objects": lambda x: f"{int(float(x)):,}" if str(x).strip() != "" else x,
                "Cold STANDARD (Objects)": lambda x: f"{int(float(x)):,}" if str(x).strip() != "" else x,
            },
            highlight_rules={"Status": _status_badge, "Lifecycle Config": _bool_badge},
        )


# ---------- helpers for highlight_rules ----------

def _status_badge(v):
    """Return 🟢/🔴/⚪ based on status or recommendation-like value."""
    s = str(v).strip()
    if s.upper() == "OK" or "🟢" in s:
        return "🟢 OK"
    if s == "" or s.lower() == "none":
        return "⚪ Unknown"
    return "🔴 Action"


def _bool_badge(v):
    """Return textual badge for boolean-ish values."""
    s = str(v).strip().lower()
    if s in {"true", "1", "yes"}:
        return "🟢 Yes"
    if s in {"false", "0", "no"}:
        return "🔴 No"
    return v


# Allow running as a Streamlit multipage without main app router
def _maybe_render_self():
    # Only run if called directly by Streamlit multipage (no router passed frames)
    if st.runtime.exists():  # type: ignore[attr-defined]
        debug_write("🔍 **DEBUG:** Dashboard self-render called")
        ec2_df = st.session_state.get("ec2_df")
        s3_df = st.session_state.get("s3_df")
        debug_write(f"   - Retrieved EC2 data: {ec2_df.shape if ec2_df is not None and not ec2_df.empty else 'EMPTY/NONE'}")
        debug_write(f"   - Retrieved S3 data: {s3_df.shape if s3_df is not None and not s3_df.empty else 'EMPTY/NONE'}")
        # Fallback formatters and components if not provided by app router
        try:
            from cwt_ui.components import cards as _cards
        except Exception:
            class _Cards:
                @staticmethod
                def metric(label, value, help_text=None):
                    st.metric(label, value, help=help_text)
            _cards = _Cards()
        try:
            from cwt_ui.components import tables as _tables
        except Exception:
            class _Tables:
                @staticmethod
                def render(df: pd.DataFrame, **_):
                    st.dataframe(df, use_container_width=True)
            _tables = _Tables()
        try:
            from cwt_ui.services import formatters as _formatters
        except Exception:
            class _Fmt:
                @staticmethod
                def currency(x):
                    try: return f"${float(x):,.2f}"
                    except Exception: return str(x)
                @staticmethod
                def percent(x, d: int = 2):
                    try: return f"{float(x):.{d}f}%"
                    except Exception: return str(x)
                @staticmethod
                def human_gb(x, d: int = 2):
                    try: return f"{float(x):.{d}f} GB"
                    except Exception: return str(x)
            _formatters = _Fmt()
        if ec2_df is None:
            ec2_df = pd.DataFrame()
        if s3_df is None:
            s3_df = pd.DataFrame()
        
        # If no data in session state, try to load from database
        if ec2_df.empty and s3_df.empty:
            try:
                from db.repo import get_last_scan
                ec2_df, s3_df, scanned_at = get_last_scan()
                if not ec2_df.empty or not s3_df.empty:
                    debug_write("🔍 **DEBUG:** Loaded data from database on page load")
                    # Update session state
                    st.session_state["ec2_df"] = ec2_df
                    st.session_state["s3_df"] = s3_df
                    st.session_state["last_scan_at"] = scanned_at
            except Exception as e:
                debug_write(f"🔍 **DEBUG:** Failed to load from database: {e}")
        
        render(ec2_df, s3_df, _cards, _tables, _formatters)


_maybe_render_self()
