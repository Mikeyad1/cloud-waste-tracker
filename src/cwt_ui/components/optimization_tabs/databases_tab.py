# Optimization > Databases (RDS, DynamoDB) tab
from __future__ import annotations

import pandas as pd
import streamlit as st

from cwt_ui.components.ui.overview_cards import render_sec_card
from cwt_ui.utils.money import format_usd


def render_databases_tab() -> None:
    db_df = st.session_state.get("databases_df", pd.DataFrame())
    data_source = st.session_state.get("data_source", "none")
    if db_df is None or db_df.empty:
        if data_source == "synthetic":
            st.info("Database data not loaded. Reload synthetic data from **Overview**.")
        else:
            st.info("**Database** (RDS, DynamoDB) optimization requires Cost Explorer or CUR data. Load **synthetic data** from Overview to explore this tab.")
        return
    total_cost = db_df["monthly_cost_usd"].sum()
    total_savings = db_df["potential_savings_usd"].sum()
    action_count = (db_df["potential_savings_usd"] > 0).sum()
    st.markdown("#### Filters")
    regions = sorted(db_df["region"].dropna().unique().tolist())
    services = sorted(db_df["service"].dropna().unique().tolist())
    col1, col2 = st.columns(2)
    with col1:
        selected_regions = st.multiselect("Region", options=regions, default=regions, key="db_tab_regions")
    with col2:
        selected_services = st.multiselect("Service", options=services, default=services, key="db_tab_service")
    filtered = db_df[db_df["region"].isin(selected_regions) & db_df["service"].isin(selected_services)]
    if filtered.empty:
        st.warning("No databases match your filters.")
        return
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    with kpi_col1:
        render_sec_card("Monthly spend", format_usd(filtered["monthly_cost_usd"].sum()), "RDS and DynamoDB cost.")
    with kpi_col2:
        render_sec_card("Potential savings", format_usd(filtered["potential_savings_usd"].sum()), "From instance or mode changes.")
    with kpi_col3:
        render_sec_card("Recommendations", action_count, "Databases with optimization suggestions.")
    st.markdown("#### RDS & DynamoDB")
    display_df = filtered[["resource_id", "service", "instance_type", "region", "monthly_cost_usd", "recommendation", "potential_savings_usd"]].copy()
    display_df.columns = ["Resource ID", "Service", "Instance / mode", "Region", "Monthly cost", "Recommendation", "Potential savings"]
    display_df["Monthly cost"] = display_df["Monthly cost"].apply(lambda x: format_usd(x))
    display_df["Potential savings"] = display_df["Potential savings"].apply(lambda x: format_usd(x))
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    if data_source == "synthetic":
        st.caption("Synthetic data. Real database optimization requires Cost Explorer, CUR, or RDS/DynamoDB APIs.")
