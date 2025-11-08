"""
Scan service component for running AWS scans.
Handles the actual scanning functionality and updates session state.
"""

import streamlit as st
import pandas as pd
import os
from typing import Tuple, Optional, Dict, Any, List

from cwt_ui.services.scans import fetch_savings_plan_utilization


def run_aws_scan(region: Optional[str] | List[str] | None = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run AWS scan for specified region(s) or globally.
    
    Args:
        region: AWS region(s) to scan. Can be:
            - None: Auto-discover and scan all enabled regions (global scan)
            - Single region string (e.g., "us-east-1"): Scan only that region
            - List of regions: Scan multiple specific regions
    
    Returns:
        Tuple of (EC2 DataFrame, S3 DataFrame) with results from scanned regions
    """
    
    # Show loading state with region info
    if isinstance(region, list):
        scan_text = f"🔍 Scanning {len(region)} regions: {', '.join(region)}..."
    elif isinstance(region, str):
        scan_text = f"🔍 Scanning {region}..."
    else:
        scan_text = "🔍 Discovering and scanning all enabled regions automatically..."
    
    with st.spinner(scan_text):
        try:
            # Import the scans service
            try:
                from cwt_ui.services.enhanced_scans import run_all_scans
            except ImportError:
                from cwt_ui.services.scans import run_all_scans
            
            # Prepare AWS credentials
            aws_credentials = {}
            aws_auth_method = st.session_state.get("aws_auth_method", "role")  # Default to role
            
            if st.session_state.get("aws_override_enabled", False):
                # Use session-scoped role configuration
                default_region = None
                if isinstance(region, list) and region:
                    default_region = region[0]
                elif isinstance(region, str):
                    default_region = region
                else:
                    default_region = st.session_state.get("aws_default_region", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
                
                # For role-based auth, base credentials come from environment variables
                if st.session_state.get("aws_auth_method") == "role":
                    aws_auth_method = "role"
                    aws_credentials = {
                        "AWS_DEFAULT_REGION": default_region
                    }
                    # Add role-specific fields
                    if st.session_state.get("aws_role_arn"):
                        aws_credentials["AWS_ROLE_ARN"] = st.session_state.get("aws_role_arn", "")
                        aws_credentials["AWS_EXTERNAL_ID"] = st.session_state.get("aws_external_id", "")
                        aws_credentials["AWS_ROLE_SESSION_NAME"] = st.session_state.get("aws_role_session_name", "CloudWasteTracker")
                else:
                    # Legacy: IAM User auth (if needed for backward compatibility)
                    aws_auth_method = "user"
                    aws_credentials = {
                        "AWS_ACCESS_KEY_ID": st.session_state.get("aws_access_key_id", ""),
                        "AWS_SECRET_ACCESS_KEY": st.session_state.get("aws_secret_access_key", ""),
                        "AWS_SESSION_TOKEN": st.session_state.get("aws_session_token", ""),
                        "AWS_DEFAULT_REGION": default_region
                    }
            else:
                # No override - use environment variables directly
                # Default to role if role ARN is in environment, otherwise user
                if os.getenv("AWS_ROLE_ARN"):
                    aws_auth_method = "role"
                else:
                    aws_auth_method = "user"
            
            # Run the scan
            ec2_df, s3_df = run_all_scans(region=region, aws_credentials=aws_credentials, aws_auth_method=aws_auth_method)
            
            # Update session state
            st.session_state["ec2_df"] = ec2_df
            st.session_state["s3_df"] = s3_df
            st.session_state["last_scan_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

            sp_df, sp_summary, sp_util_trend, sp_coverage_trend = fetch_savings_plan_utilization(
                aws_credentials if aws_credentials else None
            )
            st.session_state["SP_DF"] = sp_df
            st.session_state["SP_SUMMARY"] = sp_summary
            st.session_state["SP_UTIL_TREND"] = sp_util_trend
            st.session_state["SP_COVERAGE_TREND"] = sp_coverage_trend
            # Clear legacy keys if present
            st.session_state.pop("savings_plans_df", None)
            st.session_state.pop("savings_plans_summary", None)
            
            # Show success message with region info
            if isinstance(region, list):
                st.success(f"✅ Scan complete! Found resources in {len(region)} regions: {', '.join(region)}")
            elif isinstance(region, str):
                st.success(f"✅ Scan complete for {region}!")
            else:
                # Count unique regions in results
                regions_scanned = set()
                if not ec2_df.empty and "region" in ec2_df.columns:
                    regions_scanned.update(ec2_df["region"].unique())
                if not s3_df.empty and "region" in s3_df.columns:
                    regions_scanned.update(s3_df["region"].unique())
                if regions_scanned:
                    regions_list = sorted(list(regions_scanned))
                    st.success(f"✅ Scan complete! Discovered and scanned {len(regions_scanned)} regions: {', '.join(regions_list)}")
                else:
                    st.success("✅ Scan complete!")
            
            return ec2_df, s3_df
            
        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ Scan failed: {error_msg}")
            import traceback
            full_traceback = traceback.format_exc()
            print(f"ERROR: Full traceback:\n{full_traceback}")
            # Show exception details to help debug
            with st.expander("🔍 View Error Details"):
                st.code(full_traceback, language="python")
            return pd.DataFrame(), pd.DataFrame()


def render_scan_button(show_region_selector: bool = True) -> bool:
    """Render scan button with optional region selector.
    
    Args:
        show_region_selector: Whether to show region selection UI
    
    Returns:
        True if scan button was clicked
    """
    if show_region_selector:
        from cwt_ui.components.services.region_selector import render_region_selector
        
        st.markdown("---")
        st.markdown("### 🔍 Scan Configuration")
        
        # Render region selector
        selected_regions = render_region_selector()
        
        # Store selected regions in session state
        if selected_regions is not None:
            st.session_state["scan_regions"] = selected_regions
        else:
            st.session_state["scan_regions"] = None  # Auto-discover
    
    return st.button("🔄 Run AWS Scan", type="primary", width="stretch")
