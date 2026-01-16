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


st.set_page_config(page_title="Lambda Functions", page_icon="⚡", layout="wide")

render_page_header(
    title="Lambda Functions",
    subtitle="View and analyze your AWS Lambda functions across regions.",
    icon="⚡",
)

# Initialize session state for Lambda data
if "lambda_df" not in st.session_state:
    st.session_state["lambda_df"] = pd.DataFrame()


def filter_lambda_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply filters to Lambda DataFrame."""
    if df.empty:
        return df
    
    st.markdown("### Filters")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        regions = sorted(df["region"].dropna().unique().tolist())
        selected_regions = st.multiselect(
            "Region",
            options=regions,
            default=regions,
            help="Filter functions by AWS region.",
        )
    
    with col2:
        runtimes = sorted(df["runtime"].dropna().unique().tolist())
        selected_runtimes = st.multiselect(
            "Runtime",
            options=runtimes,
            default=runtimes,
            help="Filter functions by runtime environment.",
        )
    
    with col3:
        search_query = st.text_input(
            "Search",
            value="",
            max_chars=60,
            help="Search by function name.",
        )
    
    # Apply filters
    filtered = df.copy()
    if selected_regions:
        filtered = filtered[filtered["region"].isin(selected_regions)]
    if selected_runtimes:
        filtered = filtered[filtered["runtime"].isin(selected_runtimes)]
    if search_query:
        q = search_query.lower()
        filtered = filtered[
            filtered["function_name"].str.lower().str.contains(q, na=False)
        ]
    
    return filtered


# Main content
lambda_df = st.session_state.get("lambda_df", pd.DataFrame())

# Display results
if lambda_df.empty:
    st.info("ℹ️ **No Lambda function data found.** Run a scan from the AWS Setup page to load Lambda function data.")
    st.stop()

# Compute metrics
total_functions = len(lambda_df)
regions_count = lambda_df["region"].nunique()
runtimes_count = lambda_df["runtime"].nunique()

# Display KPIs
kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
with kpi_col1:
    st.metric("Total Functions", f"{total_functions:,}")
with kpi_col2:
    st.metric("Regions", regions_count)
with kpi_col3:
    st.metric("Runtimes", runtimes_count)

# Apply filters
filtered_df = filter_lambda_dataframe(lambda_df)

if filtered_df.empty:
    st.warning("No Lambda functions match your current filters. Adjust filters to view data.")
    st.stop()

# Display table
st.markdown("### Lambda Functions Inventory")

# Prepare table with formatted columns
table_df = filtered_df[
    [
        "function_name",
        "region",
        "runtime",
        "memory_size_mb",
        "timeout_seconds",
        "last_modified",
    ]
].copy()

# Rename columns for display
table_df.columns = [
    "Function Name",
    "Region",
    "Runtime",
    "Memory Size (MB)",
    "Timeout (seconds)",
    "Last Modified",
]

# Format last_modified for display
if "Last Modified" in table_df.columns:
    table_df["Last Modified"] = pd.to_datetime(table_df["Last Modified"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    table_df["Last Modified"] = table_df["Last Modified"].fillna("—")

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Function Name": st.column_config.TextColumn(
            "Function Name",
            help="Name of the Lambda function.",
        ),
        "Region": st.column_config.TextColumn(
            "Region",
            help="AWS region where the function is deployed.",
        ),
        "Runtime": st.column_config.TextColumn(
            "Runtime",
            help="Runtime environment (e.g., python3.11, nodejs18.x).",
        ),
        "Memory Size (MB)": st.column_config.NumberColumn(
            "Memory Size (MB)",
            format="%d",
            help="Amount of memory allocated to the function.",
        ),
        "Timeout (seconds)": st.column_config.NumberColumn(
            "Timeout (seconds)",
            format="%d",
            help="Maximum execution time in seconds.",
        ),
        "Last Modified": st.column_config.TextColumn(
            "Last Modified",
            help="Date and time when the function was last modified.",
        ),
    },
)
