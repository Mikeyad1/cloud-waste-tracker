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
st.markdown("### Other clouds")
with st.expander("GCP / Azure", expanded=False):
    st.info("**Coming later.** Google Cloud and Microsoft Azure connections will be added here.")
