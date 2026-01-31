# Optimization > Serverless (Lambda) tab
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_lambda_tab() -> None:
    lambda_df = st.session_state.get("lambda_df", pd.DataFrame())
    if lambda_df is None or lambda_df.empty:
        st.info("Run a scan from **Setup** to load Lambda function data.")
        return
    total_functions = len(lambda_df)
    regions_count = lambda_df["region"].nunique()
    runtimes_count = lambda_df["runtime"].nunique()
    st.markdown("#### Filters")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        regions = sorted(lambda_df["region"].dropna().unique().tolist())
        selected_regions = st.multiselect("Region", options=regions, default=regions, key="lambda_tab_regions")
    with col2:
        runtimes = sorted(lambda_df["runtime"].dropna().unique().tolist())
        selected_runtimes = st.multiselect("Runtime", options=runtimes, default=runtimes, key="lambda_tab_runtimes")
    with col3:
        search_query = st.text_input("Search", value="", max_chars=60, key="lambda_tab_search")
    filtered = lambda_df.copy()
    if selected_regions:
        filtered = filtered[filtered["region"].isin(selected_regions)]
    if selected_runtimes:
        filtered = filtered[filtered["runtime"].isin(selected_runtimes)]
    if search_query:
        q = search_query.lower()
        filtered = filtered[filtered["function_name"].str.lower().str.contains(q, na=False)]
    if filtered.empty:
        st.warning("No Lambda functions match your current filters.")
        return
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    with kpi_col1:
        st.metric("Total Functions", f"{len(filtered):,}")
    with kpi_col2:
        st.metric("Regions", filtered["region"].nunique())
    with kpi_col3:
        st.metric("Runtimes", filtered["runtime"].nunique())
    st.markdown("#### Lambda Functions Inventory")
    table_df = filtered[["function_name", "region", "runtime", "memory_size_mb", "timeout_seconds", "last_modified"]].copy()
    table_df.columns = ["Function Name", "Region", "Runtime", "Memory Size (MB)", "Timeout (seconds)", "Last Modified"]
    if "Last Modified" in table_df.columns:
        table_df["Last Modified"] = pd.to_datetime(table_df["Last Modified"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        table_df["Last Modified"] = table_df["Last Modified"].fillna("—")
    st.dataframe(table_df, use_container_width=True, hide_index=True)
