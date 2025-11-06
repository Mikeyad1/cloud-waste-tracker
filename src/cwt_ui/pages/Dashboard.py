import streamlit as st
import pandas as pd
import os
from cwt_ui.utils.metrics import compute_summary, render_metrics_cards, debug_write

# Load beautiful CSS
try:
    from cwt_ui.components.ui.shared_css import load_beautiful_css
    load_beautiful_css()
except:
    pass

debug_write("🔍 **DEBUG:** Dashboard page rendering")

# Beautiful header
st.markdown("""
<div class="beautiful-header">
    <h1>🚀 Cloud Waste Tracker</h1>
    <p>Optimize your AWS costs and maximize savings</p>
</div>
""", unsafe_allow_html=True)

# Get data from session state
ec2_df = st.session_state.get("ec2_df", pd.DataFrame())
s3_df = st.session_state.get("s3_df", pd.DataFrame())

has_data = not (ec2_df.empty and s3_df.empty)

# Check if we have data
if not has_data:
    st.info("No scan data available. Run a scan to see your cloud waste analysis.")
    
    # Scan controls - only show when no data
    st.markdown("### 🔍 Run AWS Scan")
    try:
        from cwt_ui.components.services.scan_service import render_scan_button, run_aws_scan
        scan_clicked = render_scan_button()
        if scan_clicked:
            # Only run scan if button was clicked
            try:
                run_aws_scan()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Scan failed: {e}")
    except Exception as e:
        # UI rendering error - show fallback button
        st.button("Run Scan", disabled=True)
        st.warning(f"⚠️ Unable to load scan controls: {e}")

# Get summary data
ec2_summary = compute_summary(ec2_df)
s3_summary = compute_summary(s3_df)

# Overall metrics
total_cost = ec2_summary["total_cost"] + s3_summary["total_cost"]
total_savings = ec2_summary["potential_savings"] + s3_summary["potential_savings"]
total_waste = ec2_summary["waste_count"] + s3_summary["waste_count"]

# Render metrics cards
render_metrics_cards(total_cost, total_savings, total_waste)

# Scan controls - only show when we have data
if has_data:
    st.markdown("### 🔍 Run New Scan")
    try:
        from cwt_ui.components.services.scan_service import render_scan_button, run_aws_scan
        scan_clicked = render_scan_button()
        if scan_clicked:
            # Only run scan if button was clicked
            try:
                run_aws_scan()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Scan failed: {e}")
    except Exception as e:
        # UI rendering error - show fallback button
        st.button("Run Scan", disabled=True)
        st.warning(f"⚠️ Unable to load scan controls: {e}")

# Resource overview
st.markdown("### 📊 Resource Overview")

# EC2 Section
if not ec2_df.empty:
    st.markdown("#### 🖥️ EC2 Instances")
    st.dataframe(ec2_df, use_container_width=True)
else:
    st.info("No EC2 data available. Run a scan to analyze your EC2 instances.")

# S3 Section
if not s3_df.empty:
    st.markdown("#### 🗄️ S3 Buckets")
    st.dataframe(s3_df, use_container_width=True)
else:
    st.info("No S3 data available. Run a scan to analyze your S3 buckets.")