import streamlit as st
import pandas as pd
import os

def debug_write(message: str):
    """Write debug message only if DEBUG_MODE is enabled."""
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    DEBUG_MODE = APP_ENV != "production"
    if DEBUG_MODE:
        st.write(message)

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

# Check if we have data
if ec2_df.empty and s3_df.empty:
    st.info("No scan data available. Run a scan to see your cloud waste analysis.")
    
    # Scan controls
    st.markdown("### 🔍 Run AWS Scan")
    try:
        from cwt_ui.components.services.scan_service import render_scan_button
        render_scan_button()
    except:
        st.button("Run Scan", disabled=True)

# Compute summary metrics
def compute_summary(df):
    if df.empty:
        return {"total_cost": 0, "potential_savings": 0, "waste_count": 0}
    
    cost_col = 'monthly_cost_usd' if 'monthly_cost_usd' in df.columns else 'Monthly Cost'
    savings_col = 'potential_savings_usd' if 'potential_savings_usd' in df.columns else 'Potential Savings USD'
    
    total_cost = df[cost_col].sum() if cost_col in df.columns else 0
    potential_savings = df[savings_col].sum() if savings_col in df.columns else 0
    waste_count = len(df)
    
    return {
        "total_cost": total_cost,
        "potential_savings": potential_savings,
        "waste_count": waste_count
    }

# Get summary data
ec2_summary = compute_summary(ec2_df)
s3_summary = compute_summary(s3_df)

# Overall metrics
total_cost = ec2_summary["total_cost"] + s3_summary["total_cost"]
total_savings = ec2_summary["potential_savings"] + s3_summary["potential_savings"]
total_waste = ec2_summary["waste_count"] + s3_summary["waste_count"]

# Beautiful metrics row
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="beautiful-metric">
        <div class="beautiful-metric-value">${total_cost:,.2f}</div>
        <div class="beautiful-metric-label">Total Monthly Cost</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="beautiful-metric">
        <div class="beautiful-metric-value">${total_savings:,.2f}</div>
        <div class="beautiful-metric-label">Potential Savings</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="beautiful-metric">
        <div class="beautiful-metric-value">{total_waste}</div>
        <div class="beautiful-metric-label">Waste Items Found</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    savings_percent = (total_savings / total_cost * 100) if total_cost > 0 else 0
    st.markdown(f"""
    <div class="beautiful-metric">
        <div class="beautiful-metric-value">{savings_percent:.1f}%</div>
        <div class="beautiful-metric-label">Savings Potential</div>
    </div>
    """, unsafe_allow_html=True)

# Scan controls
st.markdown("### 🔍 Run New Scan")
try:
    from cwt_ui.components.services.scan_service import render_scan_button
    render_scan_button()
except:
    st.button("Run Scan", disabled=True)

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