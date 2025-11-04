# src/cwt_ui/services/enhanced_scans.py
"""
Enhanced scans service that provides clear, valuable recommendations with specific dollar amounts.
This replaces the basic scans with much more valuable data.
"""

from __future__ import annotations
from typing import Tuple, Optional, Mapping, List
import pandas as pd
import os

def run_all_scans(
    region: str | List[str] | None = None, 
    aws_credentials: Optional[Mapping[str, str]] = None, 
    aws_auth_method: str = "user"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run enhanced scans with clear cost analysis and actionable recommendations.
    
    Args:
        region: AWS region(s) to scan. Can be:
            - Single region string (e.g., "us-east-1")
            - List of regions (e.g., ["us-east-1", "us-west-2"])
            - None: auto-discover and scan all enabled regions
        aws_credentials: Optional credential overrides
        aws_auth_method: "user" or "role"
    """
    # Delegate to the main scans service which handles multi-region logic
    try:
        from cwt_ui.services.scans import run_all_scans as _run_all_scans
        ec2_df, s3_df = _run_all_scans(region=region, aws_credentials=aws_credentials, aws_auth_method=aws_auth_method)
        
        # Enhance the results with better recommendations
        if not ec2_df.empty:
            ec2_df = _enhance_ec2_dataframe(ec2_df)
        if not s3_df.empty:
            s3_df = _enhance_s3_dataframe(s3_df)
        
        return ec2_df, s3_df
    except Exception as e:
        print(f"Enhanced scan error: {e}")
        return pd.DataFrame(), pd.DataFrame()


def _enhance_ec2_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Enhance EC2 DataFrame with clear recommendations."""
    if df.empty:
        return df
    return df.copy()  # Already enhanced by scanners, just pass through for now


def _enhance_s3_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Enhance S3 DataFrame with clear recommendations."""
    if df.empty:
        return df
    return df.copy()  # Already enhanced by scanners, just pass through for now


def _enhance_ec2_data(findings: list) -> pd.DataFrame:
    """Enhance EC2 data with clear recommendations and dollar amounts."""
    if not findings:
        return pd.DataFrame()
    
    df = pd.DataFrame(findings)
    
    # Add clear, actionable recommendations
    def get_clear_recommendation(row):
        cpu = row.get('avg_cpu_7d', 0)
        cost = row.get('monthly_cost_usd', 0)
        instance_type = row.get('instance_type', '')
        name = row.get('name', 'Unnamed')
        
        if cpu < 1.0:
            return f"🛑 STOP: {name} - Save ${cost:.2f}/month (CPU only {cpu:.1f}%)"
        elif cpu < 3.0:
            return f"⚠️ STOP/DOWNSIZE: {name} - Save ${cost:.2f}/month (CPU {cpu:.1f}%)"
        elif cpu < 5.0:
            return f"🔄 DOWNSIZE: {name} - Save ${cost * 0.5:.2f}/month (CPU {cpu:.1f}%)"
        else:
            return f"✅ OK: {name} - CPU usage normal ({cpu:.1f}%)"
    
    def get_priority(row):
        cpu = row.get('avg_cpu_7d', 0)
        if cpu < 1.0:
            return "🔴 HIGH"
        elif cpu < 3.0:
            return "🔴 HIGH"
        elif cpu < 5.0:
            return "🟡 MEDIUM"
        else:
            return "🟢 LOW"
    
    def get_action_steps(row):
        cpu = row.get('avg_cpu_7d', 0)
        cost = row.get('monthly_cost_usd', 0)
        instance_id = row.get('instance_id', '')
        name = row.get('name', 'Unnamed')
        
        if cpu < 5.0:
            return [
                f"1. Go to EC2 Console → Instances → {instance_id}",
                f"2. Select '{name}' and click 'Instance State' → 'Stop'",
                f"3. Confirm stop to save ${cost:.2f}/month",
                f"4. For permanent removal: 'Instance State' → 'Terminate'"
            ]
        else:
            return ["No action needed - CPU usage is normal"]
    
    # Add enhanced columns
    df['clear_recommendation'] = df.apply(get_clear_recommendation, axis=1)
    df['priority'] = df.apply(get_priority, axis=1)
    df['action_steps'] = df.apply(get_action_steps, axis=1)
    df['potential_savings_usd'] = df.apply(lambda row: 
        row.get('monthly_cost_usd', 0) if row.get('avg_cpu_7d', 0) < 5.0 else 0, axis=1)
    
    # Rename columns for clarity
    df = df.rename(columns={
        'instance_id': 'Instance ID',
        'name': 'Name',
        'instance_type': 'Instance Type',
        'region': 'Region',
        'avg_cpu_7d': 'CPU Usage (%)',
        'monthly_cost_usd': 'Monthly Cost ($)',
        'clear_recommendation': 'Recommendation',
        'potential_savings_usd': 'Potential Savings ($)'
    })
    
    return df


def _enhance_s3_data(findings: list) -> pd.DataFrame:
    """Enhance S3 data with clear recommendations and dollar amounts."""
    if not findings:
        return pd.DataFrame()
    
    df = pd.DataFrame(findings)
    
    # Filter to only bucket summaries for main display
    bucket_summaries = df[df['type'] == 's3_bucket_summary'].copy()
    
    if bucket_summaries.empty:
        return pd.DataFrame()
    
    def get_clear_recommendation(row):
        bucket = row.get('bucket', '')
        cold_gb = row.get('standard_cold_gb', 0)
        lifecycle = row.get('lifecycle_defined', False)
        total_gb = row.get('size_total_gb', 0)
        
        if not lifecycle and cold_gb > 0:
            return f"📦 OPTIMIZE: {bucket} - Save ${cold_gb * 0.01:.2f}/month (Move {cold_gb:.1f}GB cold data to IA)"
        elif not lifecycle:
            return f"⚙️ SETUP: {bucket} - Add lifecycle rules to prevent future waste"
        elif cold_gb > 0:
            return f"📦 OPTIMIZE: {bucket} - Save ${cold_gb * 0.01:.2f}/month (Move {cold_gb:.1f}GB cold data to IA)"
        else:
            return f"✅ OK: {bucket} - Well optimized"
    
    def get_priority(row):
        cold_gb = row.get('standard_cold_gb', 0)
        lifecycle = row.get('lifecycle_defined', False)
        
        if cold_gb > 10:  # More than 10GB of cold data
            return "🔴 HIGH"
        elif cold_gb > 0 or not lifecycle:
            return "🟡 MEDIUM"
        else:
            return "🟢 LOW"
    
    def get_action_steps(row):
        bucket = row.get('bucket', '')
        cold_gb = row.get('standard_cold_gb', 0)
        lifecycle = row.get('lifecycle_defined', False)
        
        steps = []
        if not lifecycle:
            steps.extend([
                f"1. Go to S3 Console → {bucket} → Management → Lifecycle",
                "2. Create rule: Transition to IA after 30 days",
                "3. Add expiration rule for old versions"
            ])
        
        if cold_gb > 0:
            steps.extend([
                f"4. Move {cold_gb:.1f}GB cold data to IA storage class",
                f"5. Potential savings: ${cold_gb * 0.01:.2f}/month"
            ])
        
        if not steps:
            steps = ["No action needed - bucket is well optimized"]
        
        return steps
    
    # Add enhanced columns
    bucket_summaries['clear_recommendation'] = bucket_summaries.apply(get_clear_recommendation, axis=1)
    bucket_summaries['priority'] = bucket_summaries.apply(get_priority, axis=1)
    bucket_summaries['action_steps'] = bucket_summaries.apply(get_action_steps, axis=1)
    bucket_summaries['potential_savings_usd'] = bucket_summaries.apply(lambda row: 
        row.get('standard_cold_gb', 0) * 0.01, axis=1)  # Approximate savings
    
    # Rename columns for clarity
    bucket_summaries = bucket_summaries.rename(columns={
        'bucket': 'Bucket',
        'region': 'Region',
        'size_total_gb': 'Total Size (GB)',
        'objects_total': 'Objects',
        'standard_cold_gb': 'Cold Data (GB)',
        'lifecycle_defined': 'Lifecycle Rules',
        'clear_recommendation': 'Recommendation',
        'potential_savings_usd': 'Potential Savings ($)'
    })
    
    return bucket_summaries


