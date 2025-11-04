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

debug_write("🔍 **DEBUG:** S3 page rendering")

# Beautiful header
st.markdown("""
<div class="beautiful-header">
    <h1>🗄️ S3 Buckets</h1>
    <p>Analyze your S3 buckets for cost optimization opportunities</p>
</div>
""", unsafe_allow_html=True)

# Get data from session state
s3_df = st.session_state.get("s3_df", pd.DataFrame())

if s3_df.empty:
    st.info("No S3 data available. Run a scan from the Dashboard to analyze your S3 buckets.")
    st.button("Go to Dashboard", on_click=lambda: st.switch_page("Dashboard"))

# Calculate metrics using the shared utility
summary = compute_summary(s3_df)
total_cost = summary["total_cost"]
potential_savings = summary["potential_savings"]
waste_count = summary["waste_count"]

# Render metrics cards
render_metrics_cards(total_cost, potential_savings, waste_count)

# Recommendations
if 'recommendation' in s3_df.columns or 'Recommendation' in s3_df.columns:
    st.markdown("### 💡 Recommendations")
    
    # Group by recommendation
    rec_col = 'recommendation' if 'recommendation' in s3_df.columns else 'Recommendation'
    priority_col = 'priority' if 'priority' in s3_df.columns else 'Priority'
    
    # Create aggregation dict based on available columns
    agg_dict = {priority_col: 'first'}
    if 'potential_savings_usd' in s3_df.columns:
        agg_dict['potential_savings_usd'] = 'sum'
    
    recommendations = s3_df.groupby(rec_col).agg(agg_dict).reset_index()
    
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
st.markdown("### 📊 S3 Buckets Details")
st.dataframe(s3_df, use_container_width=True)