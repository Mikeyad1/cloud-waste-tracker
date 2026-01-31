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

render_page_header(
    title="Spend",
    subtitle="Where money goes — by cloud, account, team, and time.",
    icon="💰",
)

total_usd, spend_df = get_spend_from_scan()

# Filters: group-by (service, region, or both)
st.markdown("### Filters")
group_by = st.radio(
    "Group by",
    options=["Service", "Region", "Service and region"],
    index=0,
    horizontal=True,
    key="spend_group_by",
)
st.caption("Data is from your last scan (EC2 + Savings Plans when available). Prior period comparison and time range come in a future update.")

# Summary row
st.markdown("---")
st.markdown("### Summary")
col1, col2 = st.columns([1, 1])
with col1:
    if total_usd > 0:
        st.metric("Total spend (from scan)", format_usd(total_usd), help="Sum of EC2 and Savings Plans spend from last scan.")
    else:
        st.metric("Total spend (from scan)", "—", "Run a scan in Setup", help="Run a scan from Setup to see spend.")
with col2:
    st.metric("Vs prior period", "—", "Coming soon", help="Requires time-series spend (e.g. Cost Explorer).")

# Build display table from spend_df
if spend_df.empty or total_usd == 0:
    st.info("No spend data yet. Run a scan from **Setup** to populate EC2 (and Savings Plans) spend.")
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
elif group_by == "Region":
    # Only rows with region != "—"
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
)
