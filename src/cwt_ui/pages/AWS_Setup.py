"""
AWS Setup page - Configure credentials and scan AWS resources.
Clean, simple guided setup flow for entering IAM credentials and testing connection.
"""

import streamlit as st
import os
from cwt_ui.components.settings.settings_config import SettingsManager
from cwt_ui.components.settings.settings_aws import render_clean_credentials_form
from cwt_ui.components.services.scan_service import run_aws_scan


def debug_write(message: str):
    """Write debug message only if DEBUG_MODE is enabled."""
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    DEBUG_MODE = APP_ENV != "production"
    if DEBUG_MODE:
        st.write(message)


def _render_scan_mode_toggle() -> str:
    """Render toggle interface for Global Scan vs Regional Scan.
    
    Returns:
        'global' or 'regional' based on user selection
    """
    # Initialize session state for scan mode
    if "scan_mode" not in st.session_state:
        st.session_state["scan_mode"] = "global"
    
    # Custom CSS for circle/tab toggle
    st.markdown("""
    <style>
        .scan-mode-container {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding: 1rem;
            background-color: #f8f9fa;
            border-radius: 8px;
            align-items: center;
        }
        .scan-mode-option {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            transition: all 0.3s ease;
            font-weight: 500;
        }
        .scan-mode-option:hover {
            background-color: #e9ecef;
        }
        .scan-mode-option.active {
            background-color: #1f77b4;
            color: white;
        }
        .scan-mode-circle {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid currentColor;
            transition: all 0.3s ease;
        }
        .scan-mode-option.active .scan-mode-circle {
            background-color: white;
            border-color: white;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Toggle buttons using columns for layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        global_active = st.session_state["scan_mode"] == "global"
        if st.button(
            "🌍 Global Scan",
            key="global_scan_toggle",
            type="primary" if global_active else "secondary",
            use_container_width=True
        ):
            st.session_state["scan_mode"] = "global"
            st.rerun()
    
    with col2:
        regional_active = st.session_state["scan_mode"] == "regional"
        if st.button(
            "📍 Regional Scan",
            key="regional_scan_toggle",
            type="primary" if regional_active else "secondary",
            use_container_width=True
        ):
            st.session_state["scan_mode"] = "regional"
            st.rerun()
    
    return st.session_state["scan_mode"]


def _group_regions_by_area(regions: list[str]) -> dict[str, list[str]]:
    """Group AWS regions by geographic area.
    
    Args:
        regions: List of AWS region codes
    
    Returns:
        Dictionary mapping area names to lists of region codes
    """
    groups = {
        "USA": [],
        "Europe": [],
        "Asia Pacific": [],
        "Middle East": [],
        "Africa": [],
        "South America": [],
        "Canada": [],
        "Other": []
    }
    
    # Define region prefixes for each group
    us_prefixes = ["us-"]
    europe_prefixes = ["eu-"]
    asia_prefixes = ["ap-", "ap-south"]
    middle_east_prefixes = ["me-"]
    africa_prefixes = ["af-"]
    south_america_prefixes = ["sa-"]
    canada_prefixes = ["ca-"]
    
    for region in regions:
        if any(region.startswith(prefix) for prefix in us_prefixes):
            groups["USA"].append(region)
        elif any(region.startswith(prefix) for prefix in europe_prefixes):
            groups["Europe"].append(region)
        elif any(region.startswith(prefix) for prefix in asia_prefixes):
            groups["Asia Pacific"].append(region)
        elif any(region.startswith(prefix) for prefix in middle_east_prefixes):
            groups["Middle East"].append(region)
        elif any(region.startswith(prefix) for prefix in africa_prefixes):
            groups["Africa"].append(region)
        elif any(region.startswith(prefix) for prefix in south_america_prefixes):
            groups["South America"].append(region)
        elif any(region.startswith(prefix) for prefix in canada_prefixes):
            groups["Canada"].append(region)
        else:
            groups["Other"].append(region)
    
    # Remove empty groups
    return {k: sorted(v) for k, v in groups.items() if v}


def _render_region_selector() -> str | None:
    """Render region dropdown for regional scan with grouped regions.
    
    Returns:
        Selected region code (e.g., 'us-east-1') or None
    """
    try:
        from core.services.region_service import discover_enabled_regions, get_region_display_name
        
        # Get current credentials for discovery
        aws_credentials = None
        aws_auth_method = st.session_state.get("aws_auth_method", "role")
        
        if st.session_state.get("aws_override_enabled", False):
            aws_auth_method = "role"
            aws_credentials = {
                "AWS_DEFAULT_REGION": st.session_state.get("aws_default_region", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
            }
        
        # Discover available regions
        try:
            available_regions = discover_enabled_regions(aws_credentials, aws_auth_method)
        except Exception as e:
            # Fallback to common regions if discovery fails (e.g., credentials not configured yet)
            from core.services.region_service import _common_regions
            available_regions = _common_regions()
            debug_write(f"⚠️ Region discovery failed (this is OK if credentials aren't configured yet): {e}")
        
        if not available_regions:
            st.warning("⚠️ Could not discover regions. Using default: us-east-1")
            available_regions = ["us-east-1"]
        
        # Initialize selected region in session state
        if "selected_region" not in st.session_state:
            st.session_state["selected_region"] = st.session_state.get("aws_default_region", "us-east-1")
        
        # Group regions by geographic area
        grouped_regions = _group_regions_by_area(available_regions)
        
        # Build ordered options list with subheadings
        region_options = {}  # Maps display string to region code
        ordered_options = []
        
        # Define display order for groups
        group_order = ["USA", "Canada", "Europe", "Asia Pacific", "Middle East", "Africa", "South America", "Other"]
        
        for group_name in group_order:
            if group_name in grouped_regions and grouped_regions[group_name]:
                # Add subheading (as a non-selectable separator)
                # Since Streamlit doesn't support optgroups, we'll use a formatted string
                subheading_key = f"━━━ {group_name} ━━━"
                # Store as a placeholder option (won't be selectable)
                region_options[subheading_key] = None  # None indicates it's a separator
                ordered_options.append(subheading_key)
                for region in grouped_regions[group_name]:
                    display_name = get_region_display_name(region)
                    # Format: "  └─ Display Name (region)"
                    option_display = f"  └─ {display_name} ({region})"
                    region_options[option_display] = region
                    ordered_options.append(option_display)
        
        # Get current selection index
        current_region = st.session_state["selected_region"]
        current_index = 0
        option_keys = ordered_options
        # Filter out None values (which are subheading separators)
        option_values = [v for v in region_options.values() if v is not None]
        
        if current_region in option_values:
            # Find the index of the option that maps to this region
            for idx, opt in enumerate(option_keys):
                if region_options[opt] == current_region:
                    current_index = idx
                    break
        
        # Render selectbox
        selected_display = st.selectbox(
            "📍 Select AWS Region",
            options=option_keys,
            index=current_index,
            key="region_selector",
            help="Choose the AWS region you want to scan. Regional scans are faster than global scans."
        )
        
        # Handle subheading selection (user clicked on a subheading)
        if selected_display.startswith("━━━"):
            # If a subheading was selected, keep the previous selection or use first region in that group
            if current_region in option_values:
                selected_region = current_region
            else:
                # Default to first available region
                selected_region = option_values[0] if option_values else "us-east-1"
            # Rerun to refresh and show a valid selection
            st.rerun()
        else:
            selected_region = region_options[selected_display]
        
        st.session_state["selected_region"] = selected_region
        
        return selected_region
        
    except Exception as e:
        st.error(f"❌ Error loading regions: {str(e)}")
        # Fallback to default region
        return "us-east-1"


def render() -> None:
    """Clean AWS Setup page render function."""
    debug_write("🔍 **DEBUG:** AWS Setup page rendering")
    
    # Apply clean CSS styling
    _render_clean_css()
    
    # Simple, clean header
    st.markdown("## 🔐 AWS Setup")
    st.markdown("Enter the IAM Role ARN to assume using your environment credentials.")
    st.markdown("---")
    
    # Initialize session state
    settings_manager = SettingsManager()
    cfg = settings_manager.load_settings()
    
    st.session_state.setdefault("aws_override_enabled", False)
    st.session_state.setdefault("aws_role_arn", "")
    st.session_state.setdefault("aws_external_id", "")
    st.session_state.setdefault("aws_default_region", os.getenv("AWS_DEFAULT_REGION", cfg.get("aws", {}).get("default_region", "us-east-1")))
    st.session_state.setdefault("aws_role_session_name", "CloudWasteTracker")
    st.session_state.setdefault("aws_auth_method", "role")
    st.session_state.setdefault("credentials_applied", False)
    
    # Step 1: Enter Role ARN
    st.markdown("### Step 1: Configure IAM Role")
    
    # Render scan mode toggle (Global vs Regional)
    scan_mode = _render_scan_mode_toggle()
    
    # Show appropriate info based on scan mode
    if scan_mode == "global":
        st.info("💡 **Global Scan:** Your environment variables (`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`) will be used to assume the IAM role. The scan will automatically discover and iterate through all enabled AWS regions. This may take longer but provides complete coverage.")
    else:
        st.info("💡 **Regional Scan:** Scan a specific AWS region for faster results. Choose your region below and scan only that region's resources.")
    
    # Clean credentials form
    credentials_applied = render_clean_credentials_form(settings_manager)
    
    # Show success message with spinner effect if credentials were just applied
    if st.session_state.get("_credentials_just_applied", False):
        st.session_state["credentials_applied"] = True
        st.session_state["_credentials_just_applied"] = False
        st.success("✅ **Role configured successfully!** Ready to test connection.")
    
    st.markdown("---")
    
    # Step 2: Test Connection
    st.markdown("### Step 2: Test AWS Connection")
    
    # Show status based on whether credentials are applied
    has_credentials = (
        st.session_state.get("credentials_applied", False) or 
        st.session_state.get("aws_override_enabled", False)
    )
    
    if has_credentials:
        if scan_mode == "global":
            status_text = "✅ **Role is configured.** Click below to scan all AWS regions globally."
        else:
            status_text = "✅ **Role is configured.** Select a region and click below to run a regional scan."
        status_bg = "#e7f5e7"
        status_border = "#28a745"
        status_text_color = "#155724"
    else:
        status_text = "⏳ **Configure your IAM Role in Step 1** to enable scanning."
        status_bg = "#f8f9fa"
        status_border = "#6c757d"
        status_text_color = "#495057"
    
    st.markdown(
        f"<div style='padding: 0.75rem 1rem; background-color: {status_bg}; border-left: 4px solid {status_border}; border-radius: 6px; margin-bottom: 1rem; color: {status_text_color};'>{status_text}</div>",
        unsafe_allow_html=True
    )
    
    # Show region selector for regional scan
    selected_region = None
    if scan_mode == "regional":
        selected_region = _render_region_selector()
        st.markdown("")
    
    # Scan button - enabled when credentials are applied
    if has_credentials:
        if scan_mode == "global":
            button_text = "🌍 Run Global Scan"
            scan_region = None
        else:
            button_text = f"📍 Run Regional Scan ({selected_region})"
            scan_region = selected_region
        
        if st.button(button_text, type="primary", use_container_width=True):
            with st.spinner("Scanning..." if scan_mode == "regional" else "Scanning all enabled AWS regions globally..."):
                try:
                    # Pass region parameter - None for global, selected region for regional
                    ec2_df, s3_df = run_aws_scan(region=scan_region)
                    
                    if not ec2_df.empty or not s3_df.empty:
                        if scan_mode == "global":
                            regions_found = sorted(ec2_df['region'].unique().tolist()) if 'region' in ec2_df.columns and not ec2_df.empty else []
                            st.success("✅ **Scan complete!** Found AWS resources.")
                            if regions_found:
                                st.info(f"📊 Found {len(ec2_df)} EC2 instances across {len(regions_found)} regions: {', '.join(regions_found)}")
                            else:
                                st.info(f"📊 Found {len(ec2_df)} EC2 instances and {len(s3_df)} S3 buckets.")
                        else:
                            st.success(f"✅ **Regional scan complete!** Found resources in {selected_region}.")
                            st.info(f"📊 Found {len(ec2_df)} EC2 instances and {len(s3_df)} S3 buckets in {selected_region}.")
                        st.balloons()
                    else:
                        # Check if there was an error in the scan
                        st.warning("⚠️ **Scan completed but no resources found.**")
                        if scan_mode == "global":
                            st.info("💡 This could mean:\n"
                                   "- No EC2 instances exist in your account\n"
                                   "- Instances exist but credentials lack permissions\n"
                                   "- Check the console/terminal for detailed error messages")
                        else:
                            st.info(f"💡 This could mean:\n"
                                   f"- No resources exist in {selected_region}\n"
                                   f"- Resources exist but credentials lack permissions\n"
                                   f"- Check the console/terminal for detailed error messages")
                except Exception as e:
                    st.error(f"❌ **Scan failed:** {str(e)}")
                    st.exception(e)
                    st.info("💡 Check the console/terminal output for detailed debug information.")
    else:
        button_text = "🌍 Run Global Scan" if scan_mode == "global" else "📍 Run Regional Scan"
        st.button(button_text, type="secondary", use_container_width=True, disabled=True)
    
    st.markdown("---")
    
    # Optional: Quick link to dashboard
    if st.session_state.get("last_scan_at"):
        st.markdown("### Ready to explore?")
        if st.button("📊 Go to Dashboard", type="secondary", use_container_width=True):
            st.info("💡 Use the sidebar to navigate to the Dashboard page for detailed analysis.")


def _render_clean_css() -> None:
    """Render clean, minimal CSS styling."""
    st.markdown("""
    <style>
        .main .block-container {
            padding-left: 2rem;
            padding-right: 2rem;
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 900px;
        }
        h2 {
            color: #1f77b4;
            margin-top: 1.5rem;
            margin-bottom: 0.5rem;
        }
        h3 {
            color: #495057;
            margin-top: 2rem;
            margin-bottom: 1rem;
            font-weight: 600;
        }
        .stButton > button {
            font-weight: 500;
            transition: all 0.2s ease;
        }
        .stButton > button:enabled:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
    </style>
    """, unsafe_allow_html=True)


# Allow running as a Streamlit multipage without main app router
def _maybe_render_self():
    if st.runtime.exists():  # type: ignore[attr-defined]
        debug_write("🔍 **DEBUG:** AWS Setup self-render called")
        render()


_maybe_render_self()
