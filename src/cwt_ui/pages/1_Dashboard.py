# src/cwt_ui/pages/1_Dashboard.py
from __future__ import annotations
import pandas as pd
import streamlit as st

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

    # KPIs
    idle_count, monthly_waste, cold_gb = _compute_summary(ec2_df, s3_df)
    # Estimated potential savings: sum of monthly cost for actionable EC2 rows
    potential_savings = 0.0
    if ec2_df is not None and not ec2_df.empty:
        mask = ~ec2_df.get("recommendation", pd.Series(index=ec2_df.index, dtype=str)).astype(str).str.upper().eq("OK")
        if "monthly_cost_usd" in ec2_df.columns:
            potential_savings = pd.to_numeric(ec2_df.loc[mask, "monthly_cost_usd"], errors="coerce").fillna(0.0).sum()
    last_scan = st.session_state.get("last_scan_at")
    c1, c2, c3 = st.columns(3)
    with c1:
        cards.metric("Idle EC2 (est.)", str(idle_count), "instances needing action")
    with c2:
        cards.metric("Est. Monthly Waste", formatters.currency(monthly_waste))
    with c3:
        cards.metric("S3 Cold GB", f"{cold_gb:,.2f}")
    c4, c5 = st.columns(2)
    with c4:
        cards.metric("Potential Savings (est.)", formatters.currency(potential_savings))
    with c5:
        cards.metric("Last Scan", last_scan or "-")

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
        ec2_df = st.session_state.get("ec2_df")
        s3_df = st.session_state.get("s3_df")
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
        render(ec2_df, s3_df, _cards, _tables, _formatters)


_maybe_render_self()
