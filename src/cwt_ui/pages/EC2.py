from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

from cwt_ui.components.kpi_card import render_kpi
from cwt_ui.components.ui.header import render_page_header
from cwt_ui.utils.money import format_usd


st.set_page_config(page_title="EC2 Instances", page_icon="🖥️", layout="wide")

render_page_header(
    title="EC2 Instances",
    subtitle="Understand cost, utilization, and optimization opportunities across your compute fleet.",
    icon="🖥️",
)

ec2_df = st.session_state.get("ec2_df", pd.DataFrame())

if ec2_df is None or ec2_df.empty:
    st.info("Run a scan from the AWS Setup page to populate EC2 instance data.")
    st.stop()


def _safe_column(df: pd.DataFrame, names: list[str], default=None):
    for name in names:
        if name in df.columns:
            return df[name]
    return pd.Series(default, index=df.index)


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["instance_id"] = _safe_column(out, ["instance_id", "InstanceId"], "unknown")
    out["region"] = _safe_column(out, ["region", "Region"], "unknown")
    out["name"] = _safe_column(out, ["name", "Name", "tag_Name"], "").fillna("")

    out["monthly_cost_usd"] = (
        pd.to_numeric(_safe_column(out, ["monthly_cost_usd", "Monthly Cost (USD)"], 0.0), errors="coerce")
        .fillna(0.0)
    )

    out["avg_cpu_7d"] = (
        pd.to_numeric(_safe_column(out, ["avg_cpu_7d", "CPU Utilization (%)"], np.nan), errors="coerce")
        .clip(lower=0, upper=100)
    )

    out["state"] = _safe_column(out, ["state", "State"], "unknown").str.title()

    out["billing_type"] = (
        _safe_column(out, ["billing_type", "Billing Type"], "On-Demand")
        .fillna("On-Demand")
        .replace({"sp": "SP-Covered", "Savings Plans": "SP-Covered"})
    )

    department_columns = [col for col in out.columns if "department" in col.lower()]
    if department_columns:
        out["department"] = out[department_columns[0]].fillna("Unassigned")
    elif "tags" in out.columns and out["tags"].notna().any():
        out["department"] = out["tags"].apply(
            lambda tags: tags.get("department", "Unassigned") if isinstance(tags, dict) else "Unassigned"
        )
    else:
        out["department"] = "Unassigned"

    if "idle_score" in out.columns:
        out["idle_score"] = pd.to_numeric(out["idle_score"], errors="coerce").fillna(0.0)
    else:
        out["idle_score"] = (1 - (out["avg_cpu_7d"] / 100.0)).clip(lower=0, upper=1) * 100

    if "potential_savings_usd" not in out.columns:
        out["potential_savings_usd"] = out["monthly_cost_usd"] * (out["idle_score"] / 100.0)

    if "scanned_at" in out.columns:
        out["scanned_at_ts"] = pd.to_datetime(out["scanned_at"], errors="coerce")
    else:
        out["scanned_at_ts"] = pd.NaT

    out["recommendation"] = _safe_column(out, ["recommendation", "Recommendation"], "Review instance sizing").fillna(
        "Review instance sizing"
    )

    return out


ec2_df = _ensure_columns(ec2_df)


def filter_ec2_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    regions = sorted(df["region"].dropna().unique().tolist())
    departments = sorted(df["department"].dropna().unique().tolist())

    st.markdown("### Filters")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        selected_regions = st.multiselect(
            "Region",
            options=regions,
            default=regions,
            help="Filter instances by AWS region.",
        )
    with col2:
        selected_departments = st.multiselect(
            "Department",
            options=departments,
            default=departments,
            help="Filter by department tag (if available).",
        )
    with col3:
        idle_only = st.toggle(
            "Show only idle instances",
            help="Show instances with idle score ≥ 70% (very low utilization).",
        )

    search_query = st.text_input(
        "Search",
        value="",
        max_chars=60,
        help="Search by instance ID or instance name.",
    )

    date_range = None
    if df["scanned_at_ts"].notna().any():
        min_date = df["scanned_at_ts"].min().date()
        max_date = df["scanned_at_ts"].max().date()
        default_start = max_date - timedelta(days=30)
        default_end = max_date
        date_range = st.date_input(
            "Scan date range",
            value=(default_start, default_end),
            min_value=min_date,
            max_value=max_date,
            help="Only include instances scanned within this date range.",
        )

    if st.button("Apply Filters"):
        st.toast("Filters updated", icon="✅")

    filtered = df.copy()
    if selected_regions:
        filtered = filtered[filtered["region"].isin(selected_regions)]
    if selected_departments:
        filtered = filtered[filtered["department"].isin(selected_departments)]
    if idle_only:
        filtered = filtered[filtered["idle_score"] >= 70]
    if search_query:
        q = search_query.lower()
        filtered = filtered[
            filtered["instance_id"].str.lower().str.contains(q)
            | filtered["name"].str.lower().str.contains(q)
        ]
    if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        if isinstance(start_date, date) and isinstance(end_date, date):
            mask = (
                filtered["scanned_at_ts"].notna()
                & (filtered["scanned_at_ts"].dt.date >= start_date)
                & (filtered["scanned_at_ts"].dt.date <= end_date)
            )
            filtered = filtered[mask]

    return filtered


filtered_df = filter_ec2_dataframe(ec2_df)

if filtered_df.empty:
    st.warning("No EC2 instances match your current filters. Adjust filters to view data.")
    st.stop()


def compute_metrics(df: pd.DataFrame) -> dict[str, float]:
    total_instances = len(df)
    monthly_spend = df["monthly_cost_usd"].sum()

    if df["billing_type"].notna().any():
        covered = df["billing_type"].str.contains("SP", case=False, na=False)
        coverage_pct = (covered.sum() / total_instances) * 100 if total_instances else 0.0
    else:
        coverage_pct = 0.0

    idle_mask = df["idle_score"] >= 70
    idle_cost = df.loc[idle_mask, "monthly_cost_usd"].sum()

    return {
        "total_instances": total_instances,
        "monthly_spend": monthly_spend,
        "coverage_pct": coverage_pct,
        "idle_cost": idle_cost,
    }


metrics = compute_metrics(filtered_df)

kpi_cols = st.columns(4)
with kpi_cols[0]:
    render_kpi(
        "Total EC2 Instances",
        f"{metrics['total_instances']:,}",
        help_text="Number of EC2 instances after filters.",
    )
with kpi_cols[1]:
    render_kpi(
        "Monthly EC2 Spend",
        format_usd(metrics["monthly_spend"]),
        help_text="Approximate monthly cost for filtered instances.",
    )
with kpi_cols[2]:
    render_kpi(
        "% Covered by Savings Plans",
        f"{metrics['coverage_pct']:.1f}%",
        help_text="Percentage of instances covered by Savings Plans.",
    )
with kpi_cols[3]:
    render_kpi(
        "Estimated Idle/Waste Cost",
        format_usd(metrics["idle_cost"]),
        help_text="Monthly cost from highly idle instances.",
    )


def prepare_table(df: pd.DataFrame) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "Instance ID": df["instance_id"],
            "Region": df["region"],
            "Name/Tag": df["name"].replace("", "—"),
            "Monthly Cost ($)": df["monthly_cost_usd"],
            "State": df["state"],
            "CPU Utilization (%)": df["avg_cpu_7d"].fillna(0.0),
            "Idle Score": df["idle_score"].round(1),
            "Billing Type": df["billing_type"],
            "Recommendation": df["recommendation"],
            "Potential Savings ($)": df["potential_savings_usd"],
        }
    )

    def badge_from_row(row):
        if row["Idle Score"] >= 85:
            return "🔴 High Idle"
        if row["Recommendation"] and "rightsize" in row["Recommendation"].lower():
            return "🟠 Rightsize"
        return ""

    table["Issue Badge"] = table.apply(badge_from_row, axis=1)
    return table


table_df = prepare_table(filtered_df)

st.markdown("### EC2 Inventory")

st.dataframe(
    table_df,
    width="stretch",
    hide_index=True,
    column_config={
        "Monthly Cost ($)": st.column_config.NumberColumn(
            "Monthly Cost ($)", format="$%.2f", help="Estimated monthly spend for the instance."
        ),
        "CPU Utilization (%)": st.column_config.ProgressColumn(
            "CPU Utilization (%)",
            min_value=0,
            max_value=100,
            format="%.1f%%",
            help="Average CPU utilization over the last 7 days.",
        ),
        "Idle Score": st.column_config.ProgressColumn(
            "Idle Score",
            min_value=0,
            max_value=100,
            format="%.1f",
            help="Higher scores indicate greater idle time.",
        ),
        "Issue Badge": st.column_config.TextColumn(
            "Issue",
            help="Quick indicator of important follow-up actions.",
        ),
        "Potential Savings ($)": st.column_config.NumberColumn(
            "Potential Savings ($)",
            format="$%.2f",
            help="Estimated savings if the recommendation is applied.",
        ),
    },
)

st.markdown("---")

with st.expander("View Recommendation Details"):
    instance_options = table_df["Instance ID"].tolist()
    selected_instance: Optional[str] = st.selectbox("Select instance", instance_options)
    if selected_instance:
        instance_row = table_df.loc[table_df["Instance ID"] == selected_instance].iloc[0]
        if st.button("View Recommendation Details", key="view_recommendation"):
            detail_container = st.container()
            with detail_container:
                st.markdown(f"#### Optimization Plan for {selected_instance}")
                st.markdown(
                    f"""
                    **Region:** {instance_row['Region']}  
                    **Monthly Cost:** {format_usd(instance_row['Monthly Cost ($)'])}  
                    **CPU Utilization:** {instance_row['CPU Utilization (%)']:.1f}%  
                    **Idle Score:** {instance_row['Idle Score']:.1f}
                    """
                )
                st.markdown(f"**Recommendation:** {instance_row['Recommendation']}")
                st.markdown(f"**Potential Savings:** {format_usd(instance_row['Potential Savings ($)'])}")
                if st.button("Mark as Reviewed", key="mark_reviewed"):
                    st.toast(f"{selected_instance} marked as reviewed.", icon="✅")
