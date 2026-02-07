# pages/0_Setup.py — Setup (connect clouds)
from __future__ import annotations

import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
for candidate in [CURRENT_DIR, *CURRENT_DIR.parents]:
    candidate_src = candidate / "src"
    if candidate_src.exists():
        if str(candidate_src) not in sys.path:
            sys.path.insert(0, str(candidate_src))
        break

import streamlit as st
from cwt_ui.components.ui.header import render_page_header
from cwt_ui.components.setup_aws_content import render_aws_setup_content

st.set_page_config(page_title="Setup", page_icon="🔐", layout="wide")

render_page_header(
    title="Setup",
    subtitle="Connect clouds and configure access.",
    icon="🔐",
)

st.markdown("### AWS")
render_aws_setup_content()

st.markdown("---")
st.markdown("### Connect real spend data")
with st.expander("Cost Explorer API vs CUR — what we support", expanded=False):
    st.markdown("""
    **Where does spend data come from?** Today, scans pull EC2 and Savings Plans. For full spend visibility
    (S3, RDS, Lambda, Data Transfer, etc.), you need one of these:

    | Source | What it provides | Status |
    |--------|------------------|--------|
    | **Cost Explorer API** | Hourly/daily spend by service, region, tag. Real-time. | Planned |
    | **CUR (Cost and Usage Report)** | Detailed line items in S3. Best for chargeback, custom analysis. | Planned |
    | **Cost Explorer CSV export** | Manual upload for quick start. | Planned |

    **CUR** is the gold standard for FinOps: granular line items, cost allocation tags, usage types.
    **Cost Explorer API** is faster to connect but less granular. We will support both; CUR unlocks
    chargeback, budgets, and full optimization across all services.
    """)
    st.caption("Set up CUR in AWS Billing → Cost & Usage Reports. Enable cost allocation tags (Environment, Team, CostCenter) for best results.")

st.markdown("---")
st.markdown("### Other clouds")
with st.expander("GCP / Azure", expanded=False):
    st.info("**Coming later.** Google Cloud and Microsoft Azure connections will be added here.")
