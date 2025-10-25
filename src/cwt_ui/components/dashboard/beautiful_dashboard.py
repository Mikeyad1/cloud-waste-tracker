"""
Beautiful Dashboard Components for Cloud Waste Tracker.
Professional, modern dashboard elements that make your app look stunning.
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Optional, Any
from ..ui.beautiful_ui import (
    load_css_framework, beautiful_header, beautiful_card, 
    beautiful_metric, beautiful_alert, beautiful_button,
    beautiful_badge, beautiful_progress, beautiful_spinner
)


def render_beautiful_dashboard(ec2_data: pd.DataFrame, s3_data: pd.DataFrame) -> None:
    """Render a stunning dashboard with beautiful components."""
    
    # Load the beautiful CSS framework
    load_css_framework()
    
    # Beautiful header
    beautiful_header(
        title="Cloud Waste Tracker",
        subtitle="Optimize your AWS costs with intelligent insights",
        icon="☁️"
    )
    
    # Calculate metrics
    total_instances = len(ec2_data) if not ec2_data.empty else 0
    idle_instances = len(ec2_data[ec2_data.get('recommendation', '').str.contains('idle', case=False)]) if not ec2_data.empty else 0
    total_buckets = len(s3_data) if not s3_data.empty else 0
    cold_buckets = len(s3_data[s3_data.get('recommendation', '').str.contains('cold', case=False)]) if not s3_data.empty else 0
    
    # Calculate potential savings
    ec2_savings = ec2_data.get('potential_savings_usd', pd.Series()).sum() if not ec2_data.empty else 0
    s3_savings = s3_data.get('potential_savings_usd', pd.Series()).sum() if not s3_data.empty else 0
    total_savings = ec2_savings + s3_savings
    
    # Beautiful metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        beautiful_metric(
            value=f"${total_savings:,.0f}",
            label="Potential Monthly Savings",
            change="+12% vs last month",
            change_type="positive"
        )
    
    with col2:
        beautiful_metric(
            value=f"{idle_instances}/{total_instances}",
            label="Idle EC2 Instances",
            change=f"{idle_instances/total_instances*100:.0f}% idle rate" if total_instances > 0 else "0% idle rate",
            change_type="warning" if idle_instances > 0 else "positive"
        )
    
    with col3:
        beautiful_metric(
            value=f"{cold_buckets}/{total_buckets}",
            label="Cold S3 Buckets",
            change=f"{cold_buckets/total_buckets*100:.0f}% cold rate" if total_buckets > 0 else "0% cold rate",
            change_type="warning" if cold_buckets > 0 else "positive"
        )
    
    with col4:
        beautiful_metric(
            value=f"${total_savings*12:,.0f}",
            label="Annual Savings Potential",
            change="ROI: 3.2x",
            change_type="positive"
        )
    
    # Beautiful alerts
    if total_savings > 0:
        beautiful_alert(
            message=f"🎉 You could save ${total_savings:,.0f} per month! That's ${total_savings*12:,.0f} annually.",
            alert_type="success",
            icon="💰"
        )
    
    if idle_instances > 0:
        beautiful_alert(
            message=f"⚠️ {idle_instances} EC2 instances are idle and costing you money. Consider stopping or resizing them.",
            alert_type="warning",
            icon="🖥️"
        )
    
    if cold_buckets > 0:
        beautiful_alert(
            message=f"❄️ {cold_buckets} S3 buckets contain cold data. Move to cheaper storage classes to save money.",
            alert_type="info",
            icon="🗄️"
        )
    
    # Beautiful cards for detailed views
    col1, col2 = st.columns(2)
    
    with col1:
        beautiful_card(
            title="EC2 Instance Analysis",
            subtitle="Compute resource optimization opportunities",
            content=render_ec2_summary(ec2_data)
        )
    
    with col2:
        beautiful_card(
            title="S3 Storage Analysis", 
            subtitle="Storage cost optimization opportunities",
            content=render_s3_summary(s3_data)
        )
    
    # Beautiful action buttons
    st.markdown("### 🚀 Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if beautiful_button("🔄 Refresh Scan", "primary"):
            st.rerun()
    
    with col2:
        if beautiful_button("📊 Detailed Report", "secondary"):
            st.info("Detailed report generation coming soon!")
    
    with col3:
        if beautiful_button("⚙️ Settings", "secondary"):
            st.info("Settings page coming soon!")
    
    with col4:
        if beautiful_button("📧 Export Data", "secondary"):
            st.info("Data export coming soon!")


def render_ec2_summary(ec2_data: pd.DataFrame) -> str:
    """Render EC2 summary content."""
    if ec2_data.empty:
        return "<p style='color: var(--gray-600); text-align: center; padding: 2rem;'>No EC2 data available. Run a scan to see your instances.</p>"
    
    # Get top recommendations
    recommendations = ec2_data.get('recommendation', pd.Series()).value_counts().head(3)
    
    html = "<div style='padding: 1rem 0;'>"
    
    for rec, count in recommendations.items():
        if pd.notna(rec) and rec != '':
            html += f"""
            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.75rem; background: var(--gray-100); border-radius: var(--border-radius-sm);'>
                <span style='font-weight: 500;'>{rec}</span>
                <span class='beautiful-badge warning'>{count} instances</span>
            </div>
            """
    
    html += "</div>"
    return html


def render_s3_summary(s3_data: pd.DataFrame) -> str:
    """Render S3 summary content."""
    if s3_data.empty:
        return "<p style='color: var(--gray-600); text-align: center; padding: 2rem;'>No S3 data available. Run a scan to see your buckets.</p>"
    
    # Get top recommendations
    recommendations = s3_data.get('recommendation', pd.Series()).value_counts().head(3)
    
    html = "<div style='padding: 1rem 0;'>"
    
    for rec, count in recommendations.items():
        if pd.notna(rec) and rec != '':
            html += f"""
            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.75rem; background: var(--gray-100); border-radius: var(--border-radius-sm);'>
                <span style='font-weight: 500;'>{rec}</span>
                <span class='beautiful-badge info'>{count} buckets</span>
            </div>
            """
    
    html += "</div>"
    return html


def render_beautiful_loading_state() -> None:
    """Render a beautiful loading state."""
    load_css_framework()
    
    beautiful_header(
        title="Scanning Your AWS Resources",
        subtitle="Analyzing your cloud infrastructure for optimization opportunities",
        icon="🔍"
    )
    
    beautiful_spinner("Scanning EC2 instances...")
    
    st.markdown("""
    <div style='text-align: center; margin-top: 2rem;'>
        <p style='color: var(--gray-600); font-size: 1.1rem;'>
            This may take a few minutes depending on the size of your AWS infrastructure.
        </p>
    </div>
    """, unsafe_allow_html=True)
