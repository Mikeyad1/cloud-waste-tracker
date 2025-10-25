"""
Beautiful Demo Page - Showcase of what's possible with Streamlit.
This demonstrates the stunning UI components we can create.
"""

import streamlit as st
import pandas as pd
import numpy as np
from cwt_ui.components.dashboard.beautiful_dashboard import render_beautiful_dashboard, render_beautiful_loading_state
from cwt_ui.components.ui.beautiful_ui import (
    load_css_framework, beautiful_header, beautiful_card, 
    beautiful_metric, beautiful_alert, beautiful_button,
    beautiful_badge, beautiful_progress, beautiful_spinner
)


def render_demo_page() -> None:
    """Render a stunning demo page showcasing beautiful components."""
    
    # Load the beautiful CSS framework
    load_css_framework()
    
    # Beautiful header
    beautiful_header(
        title="Beautiful UI Demo",
        subtitle="See what's possible with Streamlit + Custom CSS",
        icon="✨"
    )
    
    # Beautiful metrics showcase
    st.markdown("### 📊 Beautiful Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        beautiful_metric(
            value="$2,847",
            label="Monthly Savings",
            change="+23% vs last month",
            change_type="positive"
        )
    
    with col2:
        beautiful_metric(
            value="12/45",
            label="Idle Instances",
            change="27% idle rate",
            change_type="warning"
        )
    
    with col3:
        beautiful_metric(
            value="8/23",
            label="Cold Buckets",
            change="35% cold rate",
            change_type="info"
        )
    
    with col4:
        beautiful_metric(
            value="$34,164",
            label="Annual Savings",
            change="ROI: 4.2x",
            change_type="positive"
        )
    
    # Beautiful alerts showcase
    st.markdown("### 🚨 Beautiful Alerts")
    
    beautiful_alert(
        message="🎉 Great news! You could save $2,847 per month with our recommendations.",
        alert_type="success",
        icon="💰"
    )
    
    beautiful_alert(
        message="⚠️ 12 EC2 instances are idle and costing you money. Consider stopping them.",
        alert_type="warning",
        icon="🖥️"
    )
    
    beautiful_alert(
        message="❄️ 8 S3 buckets contain cold data. Move to cheaper storage classes.",
        alert_type="info",
        icon="🗄️"
    )
    
    beautiful_alert(
        message="🚨 Critical: One instance has been running for 90+ days without usage.",
        alert_type="danger",
        icon="🔥"
    )
    
    # Beautiful cards showcase
    st.markdown("### 🎴 Beautiful Cards")
    
    col1, col2 = st.columns(2)
    
    with col1:
        beautiful_card(
            title="EC2 Optimization",
            subtitle="Compute resource analysis",
            content="""
            <div style='padding: 1rem 0;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.75rem; background: var(--gray-100); border-radius: var(--border-radius-sm);'>
                    <span style='font-weight: 500;'>Stop idle instances</span>
                    <span class='beautiful-badge warning'>12 instances</span>
                </div>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.75rem; background: var(--gray-100); border-radius: var(--border-radius-sm);'>
                    <span style='font-weight: 500;'>Resize oversized instances</span>
                    <span class='beautiful-badge info'>8 instances</span>
                </div>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.75rem; background: var(--gray-100); border-radius: var(--border-radius-sm);'>
                    <span style='font-weight: 500;'>Enable auto-scaling</span>
                    <span class='beautiful-badge success'>5 instances</span>
                </div>
            </div>
            """
        )
    
    with col2:
        beautiful_card(
            title="S3 Optimization",
            subtitle="Storage cost analysis",
            content="""
            <div style='padding: 1rem 0;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.75rem; background: var(--gray-100); border-radius: var(--border-radius-sm);'>
                    <span style='font-weight: 500;'>Move to Glacier</span>
                    <span class='beautiful-badge warning'>8 buckets</span>
                </div>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.75rem; background: var(--gray-100); border-radius: var(--border-radius-sm);'>
                    <span style='font-weight: 500;'>Enable lifecycle policies</span>
                    <span class='beautiful-badge info'>15 buckets</span>
                </div>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 0.75rem; background: var(--gray-100); border-radius: var(--border-radius-sm);'>
                    <span style='font-weight: 500;'>Delete old versions</span>
                    <span class='beautiful-badge danger'>3 buckets</span>
                </div>
            </div>
            """
        )
    
    # Beautiful progress bars
    st.markdown("### 📈 Beautiful Progress Bars")
    
    beautiful_progress(75, "EC2 Optimization Progress")
    beautiful_progress(45, "S3 Optimization Progress")
    beautiful_progress(90, "Overall Cost Reduction")
    
    # Beautiful badges
    st.markdown("### 🏷️ Beautiful Badges")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        beautiful_badge("High Priority", "danger")
    
    with col2:
        beautiful_badge("Medium Priority", "warning")
    
    with col3:
        beautiful_badge("Low Priority", "info")
    
    with col4:
        beautiful_badge("Completed", "success")
    
    # Beautiful buttons
    st.markdown("### 🔘 Beautiful Buttons")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if beautiful_button("🚀 Start Scan", "primary"):
            st.success("Scan started!")
    
    with col2:
        if beautiful_button("📊 View Report", "secondary"):
            st.info("Report generated!")
    
    with col3:
        if beautiful_button("⚙️ Settings", "success"):
            st.info("Settings opened!")
    
    with col4:
        if beautiful_button("🗑️ Delete", "danger"):
            st.warning("Delete confirmed!")
    
    # Beautiful loading state
    st.markdown("### ⏳ Beautiful Loading States")
    
    if st.button("Show Loading State"):
        beautiful_spinner("Processing your request...")
    
    # Beautiful data table
    st.markdown("### 📋 Beautiful Data Table")
    
    # Create sample data
    sample_data = pd.DataFrame({
        'Instance ID': ['i-1234567890abcdef0', 'i-0987654321fedcba0', 'i-abcdef1234567890'],
        'Instance Type': ['t3.medium', 'm5.large', 'c5.xlarge'],
        'Status': ['Running', 'Stopped', 'Running'],
        'CPU Usage': ['5%', '0%', '85%'],
        'Monthly Cost': ['$45.60', '$0.00', '$156.80'],
        'Recommendation': ['Resize', 'Stop', 'OK'],
        'Priority': ['High', 'Medium', 'Low']
    })
    
    st.markdown("""
    <div class="beautiful-table">
        <table>
            <thead>
                <tr>
                    <th>Instance ID</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>CPU Usage</th>
                    <th>Monthly Cost</th>
                    <th>Recommendation</th>
                    <th>Priority</th>
                </tr>
            </thead>
            <tbody>
    """, unsafe_allow_html=True)
    
    for _, row in sample_data.iterrows():
        priority_class = "danger" if row['Priority'] == 'High' else "warning" if row['Priority'] == 'Medium' else "info"
        st.markdown(f"""
        <tr>
            <td>{row['Instance ID']}</td>
            <td>{row['Instance Type']}</td>
            <td>{row['Status']}</td>
            <td>{row['CPU Usage']}</td>
            <td>{row['Monthly Cost']}</td>
            <td>{row['Recommendation']}</td>
            <td><span class='beautiful-badge {priority_class}'>{row['Priority']}</span></td>
        </tr>
        """, unsafe_allow_html=True)
    
    st.markdown("""
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)
    
    # Beautiful footer
    st.markdown("""
    <div style='text-align: center; margin-top: 3rem; padding: 2rem; background: var(--gray-100); border-radius: var(--border-radius);'>
        <h3 style='color: var(--gray-700); margin-bottom: 1rem;'>✨ This is what's possible with Streamlit!</h3>
        <p style='color: var(--gray-600); font-size: 1.1rem;'>
            Professional, beautiful, and fully functional - all with Python and CSS.
        </p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    render_demo_page()
