# pages/2_Spend.py — Spend (where money goes)
from __future__ import annotations

import sys
from pathlib import Path

for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parent.parents]:
    if (p / "src").exists() and str(p / "src") not in sys.path:
        sys.path.insert(0, str(p / "src"))
        break

import pandas as pd
import streamlit as st

from cwt_ui.components.ui.header import render_page_header
from cwt_ui.services.spend_aggregate import get_spend_from_scan
from cwt_ui.utils.money import format_usd

st.set_page_config(page_title="Spend", page_icon="💰", layout="wide")

# Spend page CSS (consistent with Overview)
st.markdown("""
<style>
    .spend-summary-card {
        background: linear-gradient(145deg, #1a1f2e 0%, #252b3b 100%);
        border: 1px solid #2d3548;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .spend-summary-label { font-size: 0.75rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
    .spend-summary-value { font-size: 1.35rem; font-weight: 700; color: #f1f5f9; }
    .spend-summary-delta { font-size: 0.85rem; margin-top: 4px; }
    .spend-summary-delta.up { color: #22c55e; }
    .spend-summary-delta.down { color: #f59e0b; }
    .spend-data-badge { display: inline-block; background: #334155; color: #94a3b8; font-size: 0.7rem; padding: 4px 8px; border-radius: 6px; margin-left: 8px; }
    .spend-data-badge.synthetic { background: #1e3a5f; color: #7dd3fc; }
</style>
""", unsafe_allow_html=True)

render_page_header(
    title="Spend",
    subtitle="Where money goes — by cloud, account, team, and time.",
    icon="💰",
)

total_usd, spend_df = get_spend_from_scan()
last_scan_at = st.session_state.get("last_scan_at", "")
data_source = st.session_state.get("data_source", "none")
prev_spend = st.session_state.get("previous_spend_total")

# Data source indicator
if data_source == "synthetic":
    st.markdown('<span class="spend-data-badge synthetic">Using synthetic data</span>', unsafe_allow_html=True)
    st.caption("Run a scan from **Setup** to replace with live AWS data.")
if last_scan_at:
    scope = "Full service list (synthetic)" if data_source == "synthetic" else "EC2 + Savings Plans from scan"
    st.caption(f"Last scan: {last_scan_at[:16] if len(last_scan_at) > 16 else last_scan_at} · Data scope: {scope}.")

# Filters
group_by_opts = ["Service", "Region", "Service and region"]
if "category" in spend_df.columns and spend_df["category"].notna().any():
    group_by_opts = ["Service", "Category", "Region", "Service and region"]
group_by = st.radio(
    "Group by",
    options=group_by_opts,
    index=0,
    horizontal=True,
    key="spend_group_by",
    help="How to aggregate spend rows.",
)

# Summary row (cards)
st.markdown("### Summary")
col1, col2 = st.columns(2)
with col1:
    st.markdown(
        f'''
        <div class="spend-summary-card">
            <div class="spend-summary-label">Total spend (from scan)</div>
            <div class="spend-summary-value">{format_usd(total_usd) if total_usd and total_usd > 0 else "—"}</div>
            <div class="spend-summary-delta">{"Full service list (synthetic)" if data_source == "synthetic" else "EC2 + Savings Plans"}. Re-run scan to refresh.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
with col2:
    vs_value = "—"
    vs_delta = ""
    vs_class = ""
    if prev_spend is not None and total_usd is not None and total_usd > 0:
        diff = total_usd - float(prev_spend)
        if diff > 0:
            vs_value = f"+{format_usd(diff)}"
            vs_delta = "vs last scan"
            vs_class = "up"
        elif diff < 0:
            vs_value = f"-{format_usd(-diff)}"
            vs_delta = "vs last scan"
            vs_class = "down"
        else:
            vs_value = "No change"
            vs_delta = "vs last scan"
    else:
        vs_delta = "Run another scan to see change vs last run."
    st.markdown(
        f'''
        <div class="spend-summary-card">
            <div class="spend-summary-label">Vs prior period</div>
            <div class="spend-summary-value spend-summary-delta {vs_class}">{vs_value}</div>
            <div class="spend-summary-delta" style="font-size:0.8rem;color:#64748b;">{vs_delta}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.caption("Prior period = last scan. Time-series (Cost Explorer) adds month-over-month later.")

# Build display table from spend_df
if spend_df.empty or not total_usd or total_usd == 0:
    st.info("No spend data yet. Run a scan from **Setup** or load **synthetic data** from Overview to populate EC2 (and Savings Plans) spend.")
    st.stop()

# Aggregate by chosen group-by
if group_by == "Service":
    table_df = (
        spend_df.groupby("service", as_index=False)["amount_usd"]
        .sum()
        .sort_values("amount_usd", ascending=False)
    )
    table_df["pct_of_total"] = (table_df["amount_usd"] / total_usd * 100).round(1)
    table_df = table_df.rename(columns={"service": "Service", "amount_usd": "Amount ($)", "pct_of_total": "% of total"})
elif group_by == "Category":
    if "category" not in spend_df.columns:
        table_df = spend_df.groupby("service", as_index=False)["amount_usd"].sum()
        table_df["pct_of_total"] = (table_df["amount_usd"] / total_usd * 100).round(1)
        table_df = table_df.rename(columns={"service": "Service", "amount_usd": "Amount ($)", "pct_of_total": "% of total"})
    else:
        table_df = (
            spend_df.groupby("category", as_index=False)["amount_usd"]
            .sum()
            .sort_values("amount_usd", ascending=False)
        )
        table_df["pct_of_total"] = (table_df["amount_usd"] / total_usd * 100).round(1)
        table_df = table_df.rename(columns={"category": "Category", "amount_usd": "Amount ($)", "pct_of_total": "% of total"})
elif group_by == "Region":
    by_region = spend_df[spend_df["region"] != "—"]
    if by_region.empty:
        table_df = pd.DataFrame(columns=["Region", "Amount ($)", "% of total"])
        st.caption("No region breakdown (e.g. SP-only data). Use *Service* or *Service and region*.")
    else:
        table_df = (
            by_region.groupby("region", as_index=False)["amount_usd"]
            .sum()
            .sort_values("amount_usd", ascending=False)
        )
        table_df["pct_of_total"] = (table_df["amount_usd"] / total_usd * 100).round(1)
        table_df = table_df.rename(columns={"region": "Region", "amount_usd": "Amount ($)", "pct_of_total": "% of total"})
else:
    table_df = spend_df.copy()
    table_df["pct_of_total"] = (table_df["amount_usd"] / total_usd * 100).round(1)
    table_df = table_df.rename(columns={"service": "Service", "region": "Region", "amount_usd": "Amount ($)", "pct_of_total": "% of total"})
    table_df = table_df.sort_values("Amount ($)", ascending=False)

st.markdown("### Spend by " + group_by.lower())
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Amount ($)": st.column_config.NumberColumn("Amount ($)", format="$%.2f"),
        "% of total": st.column_config.NumberColumn("% of total", format="%.1f%%"),
    },
)

# Export CSV
st.markdown("---")
csv = table_df.to_csv(index=False)
st.download_button(
    label="Export CSV",
    data=csv,
    file_name="spend_export.csv",
    mime="text/csv",
    key="spend_export",
    help="Download spend breakdown as CSV.",
)
