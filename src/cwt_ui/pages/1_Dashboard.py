# src/cwt_ui/pages/1_Dashboard.py
from __future__ import annotations
import pandas as pd

def _compute_summary(ec2_df: pd.DataFrame, s3_df: pd.DataFrame):
    idle_count = 0
    monthly_waste = 0.0
    cold_gb = 0.0

    if ec2_df is not None and not ec2_df.empty:
        # Instances requiring action (anything not OK)
        mask = ~ec2_df["recommendation"].astype(str).str.upper().eq("OK")
        idle_count = int(mask.sum())
        if "monthly_cost_usd" in ec2_df.columns:
            monthly_waste = float(ec2_df.loc[mask, "monthly_cost_usd"].fillna(0).sum())

    if s3_df is not None and not s3_df.empty and "standard_cold_gb" in s3_df.columns:
        cold_gb = float(s3_df["standard_cold_gb"].fillna(0).sum())

    return idle_count, monthly_waste, cold_gb


def _prepare_ec2_table(ec2_df: pd.DataFrame) -> pd.DataFrame:
    if ec2_df is None or ec2_df.empty:
        return pd.DataFrame()
    cols = [
        "status", "instance_id", "name", "instance_type",
        "region", "avg_cpu_7d", "monthly_cost_usd", "recommendation"
    ]
    cols = [c for c in cols if c in ec2_df.columns]
    df = ec2_df[cols].copy()
    if "monthly_cost_usd" in df.columns:
        # Sort from most expensive to least
        df = df.sort_values("monthly_cost_usd", ascending=False)
    return df


def _prepare_s3_table(s3_df: pd.DataFrame) -> pd.DataFrame:
    if s3_df is None or s3_df.empty:
        return pd.DataFrame()
    cols = [
        "status", "bucket", "region",
        "size_total_gb", "objects_total",
        "standard_cold_gb", "standard_cold_objects",
        "lifecycle_defined", "recommendation", "notes"
    ]
    cols = [c for c in cols if c in s3_df.columns]
    return s3_df[cols].copy()


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
    c1, c2, c3 = st.columns(3)
    with c1:
        cards.metric("Idle EC2 (est.)", str(idle_count), "instances needing action")
    with c2:
        cards.metric("Est. Monthly Waste", formatters.currency(monthly_waste))
    with c3:
        cards.metric("S3 Cold GB", f"{cold_gb:,.2f}")

    # --- Colored subheaders ---
    st.markdown("<h3 style='margin-top:1rem;color:#4FC3F7'>EC2 – Top by Monthly Cost</h3>",
                unsafe_allow_html=True)

    # EC2
    ec2_tbl = _prepare_ec2_table(ec2_df)
    if ec2_tbl.empty:
        st.info("No EC2 data.")
    else:
        tables.render(
            ec2_tbl,
            column_order=list(ec2_tbl.columns),
            numeric_formatters={
                "monthly_cost_usd": formatters.currency,
                "avg_cpu_7d": lambda x: f"{float(x):.2f}"
            },
            highlight_rules={
                "status": _status_badge
            },
        )

    st.divider()

    st.markdown("<h3 style='margin-top:0.5rem;color:#FF7043'>S3 Buckets Summary</h3>",
                unsafe_allow_html=True)

    # S3
    s3_tbl = _prepare_s3_table(s3_df)
    if s3_tbl.empty:
        st.info("No S3 data.")
    else:
        tables.render(
            s3_tbl,
            column_order=list(s3_tbl.columns),
            numeric_formatters={
                "size_total_gb": lambda x: formatters.human_gb(x, 2),
                "standard_cold_gb": lambda x: formatters.human_gb(x, 2),
                "objects_total": lambda x: f"{int(float(x)):,}" if str(x).strip() != "" else x,
                "standard_cold_objects": lambda x: f"{int(float(x)):,}" if str(x).strip() != "" else x,
            },
            highlight_rules={
                "status": _status_badge,
                "lifecycle_defined": _bool_badge,
            },
        )


# ---------- helpers for highlight_rules ----------

def _status_badge(v):
    """
    Returns 🟢/🔴 based on status/empty.
    Accepts strings "OK"/others or an existing status value.
    """
    s = str(v).strip()
    if s.upper() == "OK" or "🟢" in s:
        return "🟢 OK"
    if s == "" or s.lower() == "none":
        return "⚪ Unknown"
    return "🔴 Action"

def _bool_badge(v):
    """
    True/False -> textual badge.
    """
    s = str(v).strip().lower()
    if s in {"true", "1", "yes"}:
        return "🟢 Yes"
    if s in {"false", "0", "no"}:
        return "🔴 No"
    return v
