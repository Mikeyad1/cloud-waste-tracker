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

import pandas as pd
import streamlit as st

from cwt_ui.components.ui.header import render_page_header


st.set_page_config(page_title="Fargate Tasks", page_icon="🚀", layout="wide")

render_page_header(
    title="Fargate Tasks",
    subtitle="View and analyze your AWS Fargate tasks across regions and clusters.",
    icon="🚀",
)

# Initialize session state for Fargate data
if "fargate_df" not in st.session_state:
    st.session_state["fargate_df"] = pd.DataFrame()


def filter_fargate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply filters to Fargate DataFrame."""
    if df.empty:
        return df
    
    st.markdown("### Filters")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        regions = sorted(df["region"].dropna().unique().tolist())
        selected_regions = st.multiselect(
            "Region",
            options=regions,
            default=regions,
            help="Filter tasks by AWS region.",
        )
    
    with col2:
        clusters = sorted(df["cluster_name"].dropna().unique().tolist())
        selected_clusters = st.multiselect(
            "Cluster",
            options=clusters,
            default=clusters,
            help="Filter tasks by ECS cluster.",
        )
    
    with col3:
        statuses = sorted(df["status"].dropna().unique().tolist())
        selected_statuses = st.multiselect(
            "Status",
            options=statuses,
            default=statuses,
            help="Filter tasks by status (RUNNING, STOPPED, etc.).",
        )
    
    with col4:
        search_query = st.text_input(
            "Search",
            value="",
            max_chars=60,
            help="Search by service name, task definition family, or cluster name.",
        )
    
    # Apply filters
    filtered = df.copy()
    if selected_regions:
        filtered = filtered[filtered["region"].isin(selected_regions)]
    if selected_clusters:
        filtered = filtered[filtered["cluster_name"].isin(selected_clusters)]
    if selected_statuses:
        filtered = filtered[filtered["status"].isin(selected_statuses)]
    if search_query:
        q = search_query.lower()
        filtered = filtered[
            filtered["service_name"].str.lower().str.contains(q, na=False) |
            filtered["task_definition_family"].str.lower().str.contains(q, na=False) |
            filtered["cluster_name"].str.lower().str.contains(q, na=False)
        ]
    
    return filtered


# Main content
fargate_df = st.session_state.get("fargate_df", pd.DataFrame())

# Display results
if fargate_df.empty:
    st.info("ℹ️ **No Fargate task data found.** Run a scan from the AWS Setup page to load Fargate task data.")
    st.stop()

# Compute metrics
total_tasks = len(fargate_df)
regions_count = fargate_df["region"].nunique()
clusters_count = fargate_df["cluster_name"].nunique()
running_tasks = len(fargate_df[fargate_df["status"] == "RUNNING"])
total_memory_gb = fargate_df["memory_mb"].sum() / 1024

# Display KPIs
kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
with kpi_col1:
    st.metric("Total Tasks", f"{total_tasks:,}")
with kpi_col2:
    st.metric("Running Tasks", f"{running_tasks:,}")
with kpi_col3:
    st.metric("Regions", regions_count)
with kpi_col4:
    st.metric("Clusters", clusters_count)
with kpi_col5:
    st.metric("Total Memory", f"{total_memory_gb:.1f} GB")

# Apply filters
filtered_df = filter_fargate_dataframe(fargate_df)

if filtered_df.empty:
    st.warning("No Fargate tasks match your current filters. Adjust filters to view data.")
    st.stop()

# Display table
st.markdown("### Fargate Tasks Inventory")

# Prepare table with formatted columns
table_df = filtered_df[
    [
        "service_name",
        "cluster_name",
        "task_definition_family",
        "region",
        "cpu",
        "memory_mb",
        "platform_version",
        "status",
        "container_names",
        "started_at",
    ]
].copy()

# Rename columns for display
table_df.columns = [
    "Service Name",
    "Cluster",
    "Task Definition",
    "Region",
    "CPU",
    "Memory (MB)",
    "Platform Version",
    "Status",
    "Containers",
    "Started At",
]

# Format started_at for display
if "Started At" in table_df.columns:
    table_df["Started At"] = pd.to_datetime(table_df["Started At"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    table_df["Started At"] = table_df["Started At"].fillna("—")

# Format CPU for display (remove empty strings, show as vCPU)
if "CPU" in table_df.columns:
    def format_cpu(cpu_val):
        if not cpu_val or cpu_val == "":
            return "—"
        try:
            cpu_int = int(cpu_val)
            if cpu_int > 0:
                return f"{cpu_int / 1024:.2f} vCPU"
            return str(cpu_val)
        except (ValueError, TypeError):
            return str(cpu_val) if cpu_val else "—"
    
    table_df["CPU"] = table_df["CPU"].apply(format_cpu)

# Format memory for display (convert MB to GB for large values)
if "Memory (MB)" in table_df.columns:
    def format_memory(mem_val):
        if pd.isna(mem_val) or mem_val == 0:
            return "—"
        try:
            mem_num = float(mem_val)
            if mem_num >= 1024:
                return f"{mem_num / 1024:.2f} GB"
            else:
                return f"{mem_num:.0f} MB"
        except (ValueError, TypeError):
            return "—"
    
    table_df["Memory"] = table_df["Memory (MB)"].apply(format_memory)
    # Replace the MB column with formatted memory
    table_df = table_df.drop(columns=["Memory (MB)"])
    # Reorder columns to put Memory after CPU
    column_order = []
    for col in table_df.columns:
        if col == "CPU":
            column_order.append("CPU")
            if "Memory" not in column_order:
                column_order.append("Memory")
        elif col != "Memory":
            column_order.append(col)
    
    # Ensure Memory is in the right place if CPU wasn't found
    if "Memory" in table_df.columns and "Memory" not in column_order:
        cpu_idx = column_order.index("CPU") if "CPU" in column_order else 0
        column_order.insert(cpu_idx + 1, "Memory")
    
    table_df = table_df[[c for c in column_order if c in table_df.columns]]

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Service Name": st.column_config.TextColumn(
            "Service Name",
            help="Name of the ECS service or 'Standalone Task' for tasks not part of a service.",
        ),
        "Cluster": st.column_config.TextColumn(
            "Cluster",
            help="ECS cluster where the task is running.",
        ),
        "Task Definition": st.column_config.TextColumn(
            "Task Definition",
            help="Task definition family name (e.g., my-app:5).",
        ),
        "Region": st.column_config.TextColumn(
            "Region",
            help="AWS region where the task is running.",
        ),
        "CPU": st.column_config.TextColumn(
            "CPU",
            help="CPU allocation in vCPU (e.g., 1024 = 1 vCPU).",
        ),
        "Memory": st.column_config.TextColumn(
            "Memory",
            help="Memory allocation in GB or MB.",
        ),
        "Platform Version": st.column_config.TextColumn(
            "Platform Version",
            help="Fargate platform version (e.g., LATEST, 1.4.0).",
        ),
        "Status": st.column_config.TextColumn(
            "Status",
            help="Current task status (RUNNING, STOPPED, etc.).",
        ),
        "Containers": st.column_config.TextColumn(
            "Containers",
            help="Container names running in the task.",
        ),
        "Started At": st.column_config.TextColumn(
            "Started At",
            help="Date and time when the task was started.",
        ),
    },
)
