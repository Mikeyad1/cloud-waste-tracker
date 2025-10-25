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

debug_write("🔍 **DEBUG:** EC2 page rendering")

# Beautiful header
st.markdown("""
<div class="beautiful-header">
    <h1>🖥️ EC2 Instances</h1>
    <p>Analyze your EC2 instances for cost optimization opportunities</p>
</div>
""", unsafe_allow_html=True)

# Get data from session state
ec2_df = st.session_state.get("ec2_df", pd.DataFrame())

if ec2_df.empty:
    st.info("No EC2 data available. Run a scan from the Dashboard to analyze your EC2 instances.")
    st.button("Go to Dashboard", on_click=lambda: st.switch_page("Dashboard"))

# KPIs
total_cost = ec2_df['monthly_cost_usd'].sum() if 'monthly_cost_usd' in ec2_df.columns else 0
potential_savings = ec2_df['potential_savings_usd'].sum() if 'potential_savings_usd' in ec2_df.columns else 0
waste_count = len(ec2_df)
savings_percent = (potential_savings / total_cost * 100) if total_cost > 0 else 0

# Beautiful metrics
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
        <div class="beautiful-metric-value">${potential_savings:,.2f}</div>
        <div class="beautiful-metric-label">Potential Savings</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="beautiful-metric">
        <div class="beautiful-metric-value">{waste_count}</div>
        <div class="beautiful-metric-label">Waste Items</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="beautiful-metric">
        <div class="beautiful-metric-value">{savings_percent:.1f}%</div>
        <div class="beautiful-metric-label">Savings Potential</div>
    </div>
    """, unsafe_allow_html=True)

# Recommendations
if 'recommendation' in ec2_df.columns or 'Recommendation' in ec2_df.columns:
    st.markdown("### 💡 Recommendations")
    
    # Group by recommendation
    rec_col = 'recommendation' if 'recommendation' in ec2_df.columns else 'Recommendation'
    priority_col = 'priority' if 'priority' in ec2_df.columns else 'Priority'
    
    # Create aggregation dict based on available columns
    agg_dict = {priority_col: 'first'}
    if 'potential_savings_usd' in ec2_df.columns:
        agg_dict['potential_savings_usd'] = 'sum'
    
    recommendations = ec2_df.groupby(rec_col).agg(agg_dict).reset_index()
    
    for _, rec in recommendations.iterrows():
        priority = rec[priority_col] if priority_col in rec.index else 'MEDIUM'
        
        priority_colors = {
            "HIGH": "danger",
            "MEDIUM": "warning", 
            "LOW": "info"
        }
        badge_color = priority_colors.get(priority.upper(), "info")
        
        st.markdown(f"""
        <div class="beautiful-card">
            <h4>🎯 {rec[rec_col]}</h4>
            <p><strong>Potential Savings:</strong> ${rec.get('potential_savings_usd', 0):,.2f}</p>
            <span class="beautiful-badge {badge_color}">{priority}</span>
        </div>
        """, unsafe_allow_html=True)

# Data table
st.markdown("### 📊 EC2 Instances Details")
st.dataframe(ec2_df, use_container_width=True)