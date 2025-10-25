"""
Scan service component for running AWS scans.
Handles the actual scanning functionality and updates session state.
"""

import streamlit as st
import pandas as pd
import os
from typing import Tuple, Optional, Dict, Any


def run_aws_scan(region: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run AWS scan and return EC2 and S3 dataframes."""
    
    # Get region from session state if not provided
    if region is None:
        region = st.session_state.get("region", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    
    # Show loading state
    with st.spinner("🔍 Scanning your AWS resources..."):
        try:
            # Import the scans service
            try:
                from cwt_ui.services.enhanced_scans import run_all_scans
            except ImportError:
                from cwt_ui.services.scans import run_all_scans
            
            # Prepare AWS credentials
            aws_credentials = {}
            aws_auth_method = "user"
            
            if st.session_state.get("aws_override_enabled", False):
                # Use session credentials
                aws_credentials = {
                    "aws_access_key_id": st.session_state.get("aws_access_key_id", ""),
                    "aws_secret_access_key": st.session_state.get("aws_secret_access_key", ""),
                    "aws_session_token": st.session_state.get("aws_session_token", ""),
                    "aws_default_region": st.session_state.get("aws_default_region", region)
                }
                aws_auth_method = st.session_state.get("aws_auth_method", "user")
            else:
                # Use environment credentials
                aws_credentials = {
                    "aws_default_region": region
                }
                aws_auth_method = "environment"
            
            # Run the scan
            ec2_df, s3_df = run_all_scans(region=region, aws_credentials=aws_credentials, aws_auth_method=aws_auth_method)
            
            # Update session state
            st.session_state["ec2_df"] = ec2_df
            st.session_state["s3_df"] = s3_df
            st.session_state["last_scan_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return ec2_df, s3_df
            
        except Exception as e:
            st.error(f"❌ Scan failed: {str(e)}")
            return pd.DataFrame(), pd.DataFrame()


def render_scan_button() -> bool:
    """Render a scan button and return True if clicked."""
    return st.button("🔄 Run AWS Scan", type="primary", use_container_width=True)


def render_scan_status() -> None:
    """Render the current scan status."""
    last_scan = st.session_state.get("last_scan_at", "Never")
    ec2_count = len(st.session_state.get("ec2_df", pd.DataFrame()))
    s3_count = len(st.session_state.get("s3_df", pd.DataFrame()))
    
    if last_scan != "Never":
        st.success(f"✅ Last scan: {last_scan} | Found {ec2_count} EC2 instances, {s3_count} S3 buckets")
    else:
        st.info("ℹ️ No scans run yet. Click 'Run AWS Scan' to analyze your resources.")
