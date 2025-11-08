import streamlit as st
import pandas as pd
from cwt_ui.utils.metrics import compute_summary, render_metrics_cards, debug_write
from cwt_ui.components.ui.header import render_page_header

debug_write("🔍 **DEBUG:** S3 page rendering")

render_page_header(
    title="S3 Buckets",
    subtitle="Analyze S3 usage and highlight opportunities to reduce storage spend.",
    icon="🗄️",
)

# Get data from session state
s3_df = st.session_state.get("s3_df", pd.DataFrame())

if s3_df.empty:
    st.info("No S3 data available. Run a scan from the AWS Setup page to analyze your S3 buckets.")
    st.stop()

# Calculate metrics using the shared utility
summary = compute_summary(s3_df)
render_metrics_cards(summary["total_cost"], summary["potential_savings"], summary["waste_count"])

# Normalize key columns with defaults to avoid missing data during aggregation
if 'priority' not in s3_df.columns and 'Priority' not in s3_df.columns:
    s3_df['Priority'] = 'MEDIUM'
if 'potential_savings_usd' not in s3_df.columns:
    s3_df['potential_savings_usd'] = 0.0
if 'recommendation' not in s3_df.columns and 'Recommendation' not in s3_df.columns:
    s3_df['Recommendation'] = s3_df.get('recommendation', 'Review bucket configuration')

st.markdown("### 💡 Recommendations")

rec_col = 'recommendation' if 'recommendation' in s3_df.columns else 'Recommendation'
priority_col = 'priority' if 'priority' in s3_df.columns else 'Priority'

agg_dict = {priority_col: 'first'}
if 'potential_savings_usd' in s3_df.columns:
    agg_dict['potential_savings_usd'] = 'sum'

recommendations = s3_df.groupby(rec_col, dropna=False).agg(agg_dict).reset_index()

priority_colors = {
    "HIGH": "danger",
    "MEDIUM": "warning",
    "LOW": "info"
}

for _, rec in recommendations.iterrows():
    priority = rec.get(priority_col, 'MEDIUM') or 'MEDIUM'
    badge_color = priority_colors.get(str(priority).upper(), "info")
    potential_savings = rec.get('potential_savings_usd', 0)
    potential_savings_display = f"${potential_savings:,.2f}" if potential_savings else "N/A"

    st.markdown(
        f"""
        <div class="beautiful-card">
            <h4>🎯 {rec[rec_col]}</h4>
            <p><strong>Potential Savings:</strong> {potential_savings_display}</p>
            <span class="beautiful-badge {badge_color}">{priority}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("### 📊 S3 Buckets Details")
st.dataframe(s3_df, width="stretch", hide_index=True)