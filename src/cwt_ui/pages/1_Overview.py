# pages/1_Overview.py — Overview (default home)
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

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

render_page_header(
    title="Overview",
    subtitle="Cross-cloud KPIs and health at a glance.",
    icon="📊",
)

# --- Data from session state (from scan) ---
ec2_df = st.session_state.get("ec2_df", pd.DataFrame())
last_scan_at = st.session_state.get("last_scan_at", "")
spend_total_usd, _ = get_spend_from_scan()

# Optimization potential and action count from EC2 scan
optimization_potential = 0.0
action_count = 0
if ec2_df is not None and not ec2_df.empty:
    # Sum potential savings (column may be potential_savings_usd or similar)
    for col in ["potential_savings_usd", "Potential Savings ($)", "potential_savings"]:
        if col in ec2_df.columns:
            optimization_potential = pd.to_numeric(ec2_df[col], errors="coerce").fillna(0).sum()
            break
    # Count recommendations that need action (not OK / No action)
    rec_col = None
    for col in ["recommendation", "Recommendation"]:
        if col in ec2_df.columns:
            rec_col = col
            break
    if rec_col:
        rec_upper = ec2_df[rec_col].astype(str).str.upper()
        action_count = int((~rec_upper.str.contains("OK|NO ACTION", na=True)).sum())

# --- KPI strip ---
st.markdown("### Key metrics")
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    if spend_total_usd > 0:
        st.metric("Total cloud spend (from scan)", format_usd(spend_total_usd), "EC2 + SP", help="Sum of EC2 and Savings Plans spend from last scan. See Spend for breakdown.")
    else:
        st.metric("Total cloud spend (from scan)", "—", "Run a scan in Setup", help="Run a scan from Setup to see spend (EC2 + SP).")
with col2:
    st.metric("Budget consumption", "—", "Coming soon", help="Requires Budgets (Phase 4).")
with col3:
    if optimization_potential > 0 or (ec2_df is not None and not ec2_df.empty):
        st.metric("Optimization potential", format_usd(optimization_potential), f"from EC2 scan", help="Estimated monthly savings from current optimization recommendations.")
    else:
        st.metric("Optimization potential", "—", "Run a scan in Setup", help="Run a scan from Setup to see potential savings.")
with col4:
    st.metric("Open violations", "—", "Coming soon", help="Requires Governance (Phase 5).")
with col5:
    if last_scan_at:
        st.metric("Last scan", last_scan_at[:16] if len(last_scan_at) > 16 else last_scan_at, "", help="Last time a scan was run from Setup.")
    else:
        st.metric("Last scan", "Never", "Run a scan in Setup", help="Run a scan from Setup to populate data.")

st.markdown("---")

# --- Spend by cloud + Spend trend ---
row1, row2 = st.columns([1, 1])
with row1:
    st.markdown("#### Spend by cloud")
    if ec2_df is not None and not ec2_df.empty:
        # We only have AWS data for now
        st.markdown("**AWS** — 100% (from scan scope)")
        st.caption("Multi-cloud breakdown will appear when Spend and other clouds are connected.")
    else:
        st.info("Run a scan from **Setup** to see cloud scope. Spend by service/account comes in Phase 3.")
with row2:
    st.markdown("#### Spend trend")
    st.markdown("— *Coming soon.*")
    st.caption("Time-series spend (e.g. daily/monthly) will appear when Spend data is connected (Phase 3).")

st.markdown("---")

# --- Alerts / highlights: top optimization recommendations ---
st.markdown("#### Top recommendations")
if ec2_df is not None and not ec2_df.empty and action_count > 0:
    # Top 1–3 by potential savings (or first few with a recommendation)
    savings_col = None
    for c in ["potential_savings_usd", "Potential Savings ($)", "potential_savings"]:
        if c in ec2_df.columns:
            savings_col = c
            break
    id_col = None
    for c in ["instance_id", "InstanceId", "Instance ID"]:
        if c in ec2_df.columns:
            id_col = c
            break
    rec_col = None
    for c in ["recommendation", "Recommendation"]:
        if c in ec2_df.columns:
            rec_col = c
            break
    if savings_col and id_col and rec_col:
        # Sort by savings descending, take top 3
        ser = pd.to_numeric(ec2_df[savings_col], errors="coerce").fillna(0)
        if ser.astype(float).sum() > 0:
            top = ec2_df.loc[ser.nlargest(3).index]
        else:
            top = ec2_df.head(3)
        for idx, row in top.iterrows():
            save_val = row.get(savings_col, 0)
            save_str = format_usd(save_val) if save_val else "—"
            st.markdown(f"- **{row.get(id_col, '—')}** — {row.get(rec_col, '—')} (est. {save_str}/mo)")
        try:
            st.page_link("pages/4_Optimization.py", label="View all in Optimization →", icon="🔧")
        except Exception:
            st.markdown("[View all in **Optimization** →](pages/4_Optimization.py)")
else:
    st.markdown("No optimization recommendations yet.")
    st.caption("Run a scan from **Setup**, then open **Optimization** to see EC2, Lambda, Fargate, and Savings Plans recommendations.")
    try:
        st.page_link("pages/0_Setup.py", label="Go to Setup →", icon="🔐")
    except Exception:
        st.markdown("[Go to **Setup** →](pages/0_Setup.py)")

st.markdown("---")

# --- Quick links (navigation) ---
st.markdown("#### Quick links")
try:
    link_col1, link_col2, link_col3, link_col4 = st.columns(4)
    with link_col1:
        st.page_link("pages/2_Spend.py", label="Spend", icon="💰", help="Where money goes (by cloud, account, team, time).")
    with link_col2:
        st.page_link("pages/3_Budgets_Forecast.py", label="Budgets & Forecast", icon="📈", help="Budgets, forecasts, variance.")
    with link_col3:
        st.page_link("pages/4_Optimization.py", label="Optimization", icon="🔧", help="Waste, rightsizing, recommendations.")
    with link_col4:
        st.page_link("pages/5_Governance.py", label="Governance", icon="🛡️", help="Policies, violations, approvals.")
except Exception:
    # Fallback if page_link not available (older Streamlit)
    st.markdown(
        "- **Spend** — Where money goes (by cloud, account, team, time)  \n"
        "- **Budgets & Forecast** — Budgets, forecasts, variance  \n"
        "- **Optimization** — Waste, rightsizing, recommendations (EC2, Lambda, Fargate, Savings Plans)  \n"
        "- **Governance** — Policies, violations, approvals"
    )
