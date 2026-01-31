# pages/4_Optimization.py — Optimization (waste, rightsizing, recommendations)
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
from cwt_ui.components.optimization_tabs import (
    render_ec2_tab,
    render_lambda_tab,
    render_fargate_tab,
    render_commitment_tab,
)

st.set_page_config(page_title="Optimization", page_icon="🔧", layout="wide")

render_page_header(
    title="Optimization",
    subtitle="Waste, rightsizing, and recommendations across compute, containers, serverless, and commitments.",
    icon="🔧",
)

# Scope selector (cloud / region / account — single cloud for now)
ec2_df = st.session_state.get("ec2_df", pd.DataFrame())
if not ec2_df.empty and "region" in ec2_df.columns:
    regions = sorted(ec2_df["region"].dropna().unique().tolist())
    if regions:
        selected_region = st.selectbox(
            "Filter by region (optional)",
            options=["All regions"] + regions,
            key="optimization_region",
        )
else:
    selected_region = "All regions"

# Summary KPIs from existing scan data
ec2_df = st.session_state.get("ec2_df", pd.DataFrame())
if not ec2_df.empty and "potential_savings_usd" in ec2_df.columns:
    total_potential = ec2_df["potential_savings_usd"].sum()
    action_count = (ec2_df.get("recommendation", pd.Series()).astype(str).str.lower().str.contains("stop|rightsize|downsize", na=False)).sum()
else:
    total_potential = 0.0
    action_count = 0
st.metric("Estimated potential savings (from EC2 scan)", f"${total_potential:,.2f}/mo", help="Sum of potential savings across EC2 recommendations.")
st.markdown("---")

# Tabs: Compute (EC2), Containers (Fargate), Serverless (Lambda), Commitment (Savings Plans + EC2 vs SP)
tab_compute, tab_containers, tab_serverless, tab_commitment = st.tabs(
    ["Compute (EC2)", "Containers (Fargate)", "Serverless (Lambda)", "Commitment (Savings Plans)"]
)
with tab_compute:
    render_ec2_tab()
with tab_containers:
    render_fargate_tab()
with tab_serverless:
    render_lambda_tab()
with tab_commitment:
    render_commitment_tab()
