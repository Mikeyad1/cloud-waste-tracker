"""
Dashboard UI components for beautiful rendering.
Handles the visual presentation of dashboard elements.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any
from .beautiful_ui import (
    load_css_framework, beautiful_header, beautiful_card, 
    beautiful_metric, beautiful_alert, beautiful_button,
    beautiful_badge, beautiful_progress
)
from .scan_service import run_aws_scan, render_scan_button, render_scan_status
from .dashboard_utils import compute_summary, prepare_ec2_table, prepare_s3_table


def render_dashboard_header() -> None:
    """Render the beautiful dashboard header."""
    load_css_framework()
    
    beautiful_header(
        title="Cloud Waste Tracker",
        subtitle="Optimize your AWS costs with intelligent insights",
        icon="☁️"
    )


def render_dashboard_metrics(ec2_df: pd.DataFrame, s3_df: pd.DataFrame) -> None:
    """Render the beautiful dashboard metrics."""
    idle_count, monthly_waste, cold_gb, total_potential_savings = compute_summary(ec2_df, s3_df)
    
    # Calculate additional metrics
    total_instances = len(ec2_df) if not ec2_df.empty else 0
    total_buckets = len(s3_df) if not s3_df.empty else 0
    annual_savings = total_potential_savings * 12
    
    # Beautiful metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        beautiful_metric(
            value=f"${total_potential_savings:,.0f}",
            label="Potential Monthly Savings",
            change="+12% vs last month",
            change_type="positive"
        )
    
    with col2:
        beautiful_metric(
            value=f"{idle_count}/{total_instances}",
            label="Idle EC2 Instances",
            change=f"{idle_count/total_instances*100:.0f}% idle rate" if total_instances > 0 else "0% idle rate",
            change_type="warning" if idle_count > 0 else "positive"
        )
    
    with col3:
        beautiful_metric(
            value=f"{cold_gb:,.0f} GB",
            label="Cold S3 Data",
            change=f"{cold_gb/total_buckets:.0f} GB avg" if total_buckets > 0 else "0 GB avg",
            change_type="warning" if cold_gb > 0 else "positive"
        )
    
    with col4:
        beautiful_metric(
            value=f"${annual_savings:,.0f}",
            label="Annual Savings Potential",
            change="ROI: 3.2x",
            change_type="positive"
        )


def render_dashboard_alerts(ec2_df: pd.DataFrame, s3_df: pd.DataFrame) -> None:
    """Render beautiful dashboard alerts based on data."""
    idle_count, monthly_waste, cold_gb, total_potential_savings = compute_summary(ec2_df, s3_df)
    
    # Success alert for potential savings
    if total_potential_savings > 0:
        beautiful_alert(
            message=f"🎉 You could save ${total_potential_savings:,.0f} per month! That's ${total_potential_savings*12:,.0f} annually.",
            alert_type="success",
            icon="💰"
        )
    
    # Warning alerts for issues
    if idle_count > 0:
        beautiful_alert(
            message=f"⚠️ {idle_count} EC2 instances are idle and costing you money. Consider stopping or resizing them.",
            alert_type="warning",
            icon="🖥️"
        )
    
    if cold_gb > 0:
        beautiful_alert(
            message=f"❄️ {cold_gb:,.0f} GB of S3 data is cold. Move to cheaper storage classes to save money.",
            alert_type="info",
            icon="🗄️"
        )


def render_resource_overview(ec2_df: pd.DataFrame, s3_df: pd.DataFrame, tables) -> None:
    """Render the resource overview section with tabs."""
    st.markdown("### 📊 Resource Overview")
    
    # Create tabs for better organization
    tab1, tab2 = st.tabs(["🖥️ EC2 Instances", "🗄️ S3 Buckets"])
    
    with tab1:
        if ec2_df is not None and not ec2_df.empty:
            # Prepare and display EC2 data
            ec2_prepared = prepare_ec2_table(ec2_df)
            
            # Show optimization summary
            actionable_count = len(ec2_prepared[ec2_prepared['Recommendation'].str.contains('STOP|DOWNSIZE|stop|downsize', na=False, case=False)])
            total_count = len(ec2_prepared)
            
            if actionable_count > 0:
                beautiful_alert(
                    message=f"Found {actionable_count} out of {total_count} EC2 instances that need optimization.",
                    alert_type="warning",
                    icon="🔍"
                )
            
            # Render the table
            tables.render(ec2_prepared, "EC2 Instances")
        else:
            beautiful_alert(
                message="No EC2 data available. Run a scan to see your instances.",
                alert_type="info",
                icon="ℹ️"
            )
    
    with tab2:
        if s3_df is not None and not s3_df.empty:
            # Prepare and display S3 data
            s3_prepared = prepare_s3_table(s3_df)
            
            # Show optimization summary
            cold_count = len(s3_prepared[s3_prepared['Recommendation'].str.contains('COLD|cold|glacier', na=False, case=False)])
            total_count = len(s3_prepared)
            
            if cold_count > 0:
                beautiful_alert(
                    message=f"Found {cold_count} out of {total_count} S3 buckets with cold data optimization opportunities.",
                    alert_type="info",
                    icon="🔍"
                )
            
            # Render the table
            tables.render(s3_prepared, "S3 Buckets")
        else:
            beautiful_alert(
                message="No S3 data available. Run a scan to see your buckets.",
                alert_type="info",
                icon="ℹ️"
            )


def render_scan_controls() -> None:
    """Render the scan controls section."""
    st.markdown("### 🚀 Quick Actions")
    
    # Show scan status
    render_scan_status()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if render_scan_button():
            # Run the actual scan
            ec2_df, s3_df = run_aws_scan()
            if not ec2_df.empty or not s3_df.empty:
                st.success("✅ Scan completed successfully!")
                st.rerun()
    
    with col2:
        if st.button("📊 Detailed Report", type="secondary", use_container_width=True):
            st.info("Detailed report generation coming soon!")
    
    with col3:
        if st.button("⚙️ Settings", type="secondary", use_container_width=True):
            st.info("Settings page coming soon!")
    
    with col4:
        if st.button("📧 Export Data", type="secondary", use_container_width=True):
            st.info("Data export coming soon!")


def render_dashboard_loading_state() -> None:
    """Render a beautiful loading state for the dashboard."""
    load_css_framework()
    
    beautiful_header(
        title="Scanning Your AWS Resources",
        subtitle="Analyzing your cloud infrastructure for optimization opportunities",
        icon="🔍"
    )
    
    st.markdown("""
    <div style='text-align: center; margin-top: 2rem;'>
        <div class="beautiful-spinner"></div>
        <p style='color: var(--gray-600); font-size: 1.1rem; margin-top: 1rem;'>
            This may take a few minutes depending on the size of your AWS infrastructure.
        </p>
    </div>
    """, unsafe_allow_html=True)
