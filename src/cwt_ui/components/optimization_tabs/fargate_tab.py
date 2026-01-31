# Optimization > Containers (Fargate) tab
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_fargate_tab() -> None:
    fargate_df = st.session_state.get("fargate_df", pd.DataFrame())
    if fargate_df is None or fargate_df.empty:
        st.info("Run a scan from **Setup** to load Fargate task data.")
        return
    st.markdown("#### Filters")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        regions = sorted(fargate_df["region"].dropna().unique().tolist())
        selected_regions = st.multiselect("Region", options=regions, default=regions, key="fargate_tab_regions")
    with col2:
        clusters = sorted(fargate_df["cluster_name"].dropna().unique().tolist())
        selected_clusters = st.multiselect("Cluster", options=clusters, default=clusters, key="fargate_tab_clusters")
    with col3:
        statuses = sorted(fargate_df["status"].dropna().unique().tolist())
        selected_statuses = st.multiselect("Status", options=statuses, default=statuses, key="fargate_tab_statuses")
    with col4:
        search_query = st.text_input("Search", value="", max_chars=60, key="fargate_tab_search")
    filtered = fargate_df.copy()
    if selected_regions:
        filtered = filtered[filtered["region"].isin(selected_regions)]
    if selected_clusters:
        filtered = filtered[filtered["cluster_name"].isin(selected_clusters)]
    if selected_statuses:
        filtered = filtered[filtered["status"].isin(selected_statuses)]
    if search_query:
        q = search_query.lower()
        filtered = filtered[
            filtered["service_name"].str.lower().str.contains(q, na=False)
            | filtered["task_definition_family"].str.lower().str.contains(q, na=False)
            | filtered["cluster_name"].str.lower().str.contains(q, na=False)
        ]
    if filtered.empty:
        st.warning("No Fargate tasks match your current filters.")
        return
    total_tasks = len(filtered)
    running_tasks = len(filtered[filtered["status"] == "RUNNING"])
    total_memory_gb = filtered["memory_mb"].sum() / 1024
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    with kpi_col1:
        st.metric("Total Tasks", f"{total_tasks:,}")
    with kpi_col2:
        st.metric("Running Tasks", f"{running_tasks:,}")
    with kpi_col3:
        st.metric("Clusters", filtered["cluster_name"].nunique())
    with kpi_col4:
        st.metric("Total Memory", f"{total_memory_gb:.1f} GB")
    st.markdown("#### Fargate Tasks Inventory")
    table_df = filtered[
        ["service_name", "cluster_name", "task_definition_family", "region", "cpu", "memory_mb", "platform_version", "status", "started_at"]
    ].copy()
    table_df.columns = ["Service Name", "Cluster", "Task Definition", "Region", "CPU", "Memory (MB)", "Platform Version", "Status", "Started At"]
    if "Started At" in table_df.columns:
        table_df["Started At"] = pd.to_datetime(table_df["Started At"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        table_df["Started At"] = table_df["Started At"].fillna("—")
    st.dataframe(table_df, use_container_width=True, hide_index=True)
