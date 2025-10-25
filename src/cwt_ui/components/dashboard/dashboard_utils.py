"""
Dashboard utility functions and data processing.
Handles data computation, summary calculations, and table preparation.
"""

import pandas as pd
from typing import Tuple, Dict, Any


def compute_summary(ec2_df: pd.DataFrame, s3_df: pd.DataFrame) -> Tuple[int, float, float, float]:
    """Return (idle_count, monthly_waste, cold_gb, total_potential_savings) from the given frames."""
    idle_count = 0
    monthly_waste = 0.0
    cold_gb = 0.0
    total_potential_savings = 0.0

    if ec2_df is not None and not ec2_df.empty:
        # Handle both old and new column names
        recommendation_col = 'Recommendation' if 'Recommendation' in ec2_df.columns else 'recommendation'
        cost_col = 'Monthly Cost ($)' if 'Monthly Cost ($)' in ec2_df.columns else 'monthly_cost_usd'
        savings_col = 'Potential Savings ($)' if 'Potential Savings ($)' in ec2_df.columns else 'potential_savings_usd'
        
        # Check for actionable recommendations (containing STOP, DOWNSIZE, etc.)
        actionable_mask = ec2_df[recommendation_col].str.contains('STOP|DOWNSIZE|stop|downsize', na=False, case=False)
        idle_count = int(actionable_mask.sum())

        # Calculate monthly waste (cost of idle instances)
        if cost_col in ec2_df.columns:
            monthly_waste = float(ec2_df.loc[actionable_mask, cost_col].sum())

        # Calculate potential savings
        if savings_col in ec2_df.columns:
            total_potential_savings += float(ec2_df[savings_col].sum())

    if s3_df is not None and not s3_df.empty:
        # Handle both old and new column names
        recommendation_col = 'Recommendation' if 'Recommendation' in s3_df.columns else 'recommendation'
        cold_col = 'Cold Data (GB)' if 'Cold Data (GB)' in s3_df.columns else 'standard_cold_gb'
        savings_col = 'Potential Savings ($)' if 'Potential Savings ($)' in s3_df.columns else 'potential_savings_usd'
        
        # Check for cold storage recommendations
        cold_mask = s3_df[recommendation_col].str.contains('COLD|cold|glacier', na=False, case=False)
        
        # Calculate cold data
        if cold_col in s3_df.columns:
            cold_gb = float(s3_df.loc[cold_mask, cold_col].sum())

        # Calculate potential savings
        if savings_col in s3_df.columns:
            total_potential_savings += float(s3_df[savings_col].sum())

    return idle_count, monthly_waste, cold_gb, total_potential_savings


def prepare_ec2_table(ec2_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare EC2 data for display with proper column handling."""
    if ec2_df is None or ec2_df.empty:
        return pd.DataFrame()

    # Handle both old and new column names
    column_mapping = {
        'Recommendation': 'Recommendation',
        'recommendation': 'Recommendation',
        'Monthly Cost ($)': 'Monthly Cost ($)',
        'monthly_cost_usd': 'Monthly Cost ($)',
        'CPU Usage (%)': 'CPU Usage (%)',
        'avg_cpu_7d': 'CPU Usage (%)',
        'Potential Savings ($)': 'Potential Savings ($)',
        'potential_savings_usd': 'Potential Savings ($)',
        'Priority': 'Priority',
        'priority': 'Priority',
        'Action': 'Action',
        'action': 'Action',
        'Implementation Steps': 'Implementation Steps',
        'implementation_steps': 'Implementation Steps',
        'ROI Days': 'ROI Days',
        'roi_days': 'ROI Days'
    }

    # Create a copy and rename columns
    df = ec2_df.copy()
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df = df.rename(columns={old_col: new_col})

    # Ensure required columns exist
    required_columns = ['Recommendation', 'Monthly Cost ($)', 'CPU Usage (%)', 'Potential Savings ($)']
    for col in required_columns:
        if col not in df.columns:
            df[col] = 'N/A'

    return df


def prepare_s3_table(s3_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare S3 data for display with proper column handling."""
    if s3_df is None or s3_df.empty:
        return pd.DataFrame()

    # Handle both old and new column names
    column_mapping = {
        'Recommendation': 'Recommendation',
        'recommendation': 'Recommendation',
        'Monthly Cost ($)': 'Monthly Cost ($)',
        'monthly_cost_usd': 'Monthly Cost ($)',
        'Cold Data (GB)': 'Cold Data (GB)',
        'standard_cold_gb': 'Cold Data (GB)',
        'Potential Savings ($)': 'Potential Savings ($)',
        'potential_savings_usd': 'Potential Savings ($)',
        'Priority': 'Priority',
        'priority': 'Priority',
        'Action': 'Action',
        'action': 'Action',
        'Implementation Steps': 'Implementation Steps',
        'implementation_steps': 'Implementation Steps',
        'ROI Days': 'ROI Days',
        'roi_days': 'ROI Days'
    }

    # Create a copy and rename columns
    df = s3_df.copy()
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df = df.rename(columns={old_col: new_col})

    # Ensure required columns exist
    required_columns = ['Recommendation', 'Monthly Cost ($)', 'Cold Data (GB)', 'Potential Savings ($)']
    for col in required_columns:
        if col not in df.columns:
            df[col] = 'N/A'

    return df


def get_status_badge(value: str) -> str:
    """Get status badge HTML for a given value."""
    if pd.isna(value) or value == '':
        return '<span class="beautiful-badge info">Unknown</span>'
    
    value_str = str(value).upper()
    if value_str in ['OK', 'HEALTHY', 'RUNNING']:
        return '<span class="beautiful-badge success">OK</span>'
    elif value_str in ['STOP', 'DOWNSIZE', 'COLD', 'GLACIER']:
        return '<span class="beautiful-badge warning">Action</span>'
    elif value_str in ['CRITICAL', 'URGENT']:
        return '<span class="beautiful-badge danger">Critical</span>'
    else:
        return f'<span class="beautiful-badge info">{value}</span>'


def get_priority_badge(value: str) -> str:
    """Get priority badge HTML for a given value."""
    if pd.isna(value) or value == '':
        return '<span class="beautiful-badge info">Unknown</span>'
    
    value_str = str(value).upper()
    if value_str in ['HIGH', 'CRITICAL', 'URGENT']:
        return '<span class="beautiful-badge danger">High</span>'
    elif value_str in ['MEDIUM', 'MODERATE']:
        return '<span class="beautiful-badge warning">Medium</span>'
    elif value_str in ['LOW', 'MINOR']:
        return '<span class="beautiful-badge info">Low</span>'
    else:
        return f'<span class="beautiful-badge info">{value}</span>'


def get_bool_badge(value: Any) -> str:
    """Get boolean badge HTML for a given value."""
    if pd.isna(value):
        return '<span class="beautiful-badge info">Unknown</span>'
    
    if isinstance(value, bool):
        return '<span class="beautiful-badge success">Yes</span>' if value else '<span class="beautiful-badge danger">No</span>'
    
    value_str = str(value).upper()
    if value_str in ['TRUE', 'YES', 'ENABLED', 'ON']:
        return '<span class="beautiful-badge success">Yes</span>'
    elif value_str in ['FALSE', 'NO', 'DISABLED', 'OFF']:
        return '<span class="beautiful-badge danger">No</span>'
    else:
        return f'<span class="beautiful-badge info">{value}</span>'
