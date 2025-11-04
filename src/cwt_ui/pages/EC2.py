"""
EC2 Instances Page - Global view of all EC2 instances across all regions.
Simple single table with exactly 6 columns.
"""

import streamlit as st
import pandas as pd
import os

# Load beautiful CSS
try:
    from cwt_ui.components.ui.shared_css import load_beautiful_css
    load_beautiful_css()
except:
    pass

# Beautiful header
st.markdown("""
<div class="beautiful-header">
    <h1>🖥️ EC2 Instances</h1>
    <p>Global view of all EC2 instances across all AWS regions</p>
</div>
""", unsafe_allow_html=True)

# Get data from session state (from global scan)
ec2_df = st.session_state.get("ec2_df", pd.DataFrame())

if ec2_df.empty:
    st.info("📭 No EC2 data available. Run a global scan from the AWS Setup page to discover instances across all regions.")
    if st.button("Go to AWS Setup", type="primary"):
        st.switch_page("pages/AWS_Setup.py")
else:
    # Prepare the simplified table with exactly 6 columns
    # Columns (exact order):
    # 1. Instance (instance_id)
    # 2. Region
    # 3. Name (Tag Name if present; otherwise empty)
    # 4. Monthly Cost (USD)
    # 5. State (running/stopped/...)
    # 6. Utilization (CPU %)
    
    # Ensure we have the required columns
    result_df = pd.DataFrame()
    
    if 'instance_id' in ec2_df.columns:
        result_df['Instance'] = ec2_df['instance_id']
    elif 'InstanceId' in ec2_df.columns:
        result_df['Instance'] = ec2_df['InstanceId']
    else:
        st.error("❌ Missing instance_id column in data")
        st.stop()
    
    # Region
    if 'region' in ec2_df.columns:
        result_df['Region'] = ec2_df['region']
    elif 'Region' in ec2_df.columns:
        result_df['Region'] = ec2_df['Region']
    else:
        result_df['Region'] = 'unknown'
    
    # Name (Tag Name or empty)
    if 'name' in ec2_df.columns:
        result_df['Name'] = ec2_df['name'].fillna('')
    elif 'Name' in ec2_df.columns:
        result_df['Name'] = ec2_df['Name'].fillna('')
    else:
        result_df['Name'] = ''
    
    # Monthly Cost (USD)
    if 'monthly_cost_usd' in ec2_df.columns:
        result_df['Monthly Cost (USD)'] = ec2_df['monthly_cost_usd'].fillna(0.0)
    elif 'Monthly Cost (USD)' in ec2_df.columns:
        result_df['Monthly Cost (USD)'] = ec2_df['Monthly Cost (USD)'].fillna(0.0)
    else:
        # Stub with 0.00 if not available
        result_df['Monthly Cost (USD)'] = 0.00
    
    # State (running/stopped/...)
    if 'state' in ec2_df.columns:
        result_df['State'] = ec2_df['state']
    elif 'State' in ec2_df.columns:
        result_df['State'] = ec2_df['State']
    else:
        # Try to infer from other columns or default
        result_df['State'] = 'unknown'
    
    # Utilization (CPU %)
    if 'avg_cpu_7d' in ec2_df.columns:
        # Format CPU: show as percentage, or "—" if unavailable (negative or -1)
        def format_cpu(cpu_val):
            if pd.isna(cpu_val) or cpu_val < 0:
                return "—"
            return f"{cpu_val:.1f}%"
        result_df['Utilization (CPU %)'] = ec2_df['avg_cpu_7d'].apply(format_cpu)
    elif 'Utilization (CPU %)' in ec2_df.columns:
        result_df['Utilization (CPU %)'] = ec2_df['Utilization (CPU %)']
    else:
        result_df['Utilization (CPU %)'] = "—"
    
    # Format Monthly Cost as currency
    result_df['Monthly Cost (USD)'] = result_df['Monthly Cost (USD)'].apply(lambda x: f"${float(x):,.2f}" if pd.notna(x) else "$0.00")
    
    # Display the table - single global table, no tabs, no filters
    st.markdown("### 📊 EC2 Instances")
    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Show summary
    total_instances = len(result_df)
    regions_count = result_df['Region'].nunique()
    st.caption(f"Showing {total_instances} instances across {regions_count} region(s)")
