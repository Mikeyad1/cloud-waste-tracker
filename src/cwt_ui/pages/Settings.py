"""
Beautiful Settings page - Refactored and organized.
This is the main Settings page that orchestrates all settings components.
"""

import streamlit as st
import os
from cwt_ui.components.settings.settings_components import (
    render_settings_header, render_info_card, render_settings_css
)
from cwt_ui.components.settings.settings_config import SettingsManager
from cwt_ui.components.settings.settings_tabs import (
    render_email_notifications_tab,
    render_aws_config_tab, 
    render_billing_tab,
    render_advanced_tab
)
from cwt_ui.components.settings.settings_aws import render_aws_credentials_section
from cwt_ui.components.services.scan_service import run_aws_scan, render_scan_status


def debug_write(message: str):
    """Write debug message only if DEBUG_MODE is enabled."""
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    DEBUG_MODE = APP_ENV != "production"
    if DEBUG_MODE:
        st.write(message)


def render() -> None:
    """Beautiful main settings page render function."""
    debug_write("🔍 **DEBUG:** Beautiful Settings page rendering")
    
    # Apply beautiful CSS styling
    render_settings_css()
    
    # Beautiful header
    render_settings_header(
        "⚙️ Settings & Configuration",
        "Customize your cloud waste tracking experience and preferences"
    )
    
    # Settings file info card
    settings_manager = SettingsManager()
    render_info_card(
        "📁 Configuration File",
        str(settings_manager.settings_path)
    )
    
    # Create tabs for better organization
    tab1, tab2, tab3, tab4 = st.tabs(["📧 Notifications", "☁️ AWS Config", "💰 Billing", "🔧 Advanced"])

    # Render each tab
    with tab1:
        render_email_notifications_tab(settings_manager)

    with tab2:
        render_aws_config_tab(settings_manager)

    with tab3:
        render_billing_tab(settings_manager)

    with tab4:
        render_advanced_tab(settings_manager)

    # AWS Credentials Section (Session Only)
    render_aws_credentials_section(settings_manager)

    # Scan Section
    st.markdown("### 🔍 Test Your AWS Connection")
    
    # Show scan status
    render_scan_status()
    
    # Scan button
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Test AWS Scan", type="primary", use_container_width=True):
            # Run a test scan
            with st.spinner("Testing your AWS connection..."):
                ec2_df, s3_df = run_aws_scan()
                if not ec2_df.empty or not s3_df.empty:
                    st.success("✅ AWS connection successful! Found resources.")
                    st.info(f"Found {len(ec2_df)} EC2 instances and {len(s3_df)} S3 buckets.")
                else:
                    st.warning("⚠️ AWS connection successful but no resources found in this region.")
            
    with col2:
        if st.button("📊 Go to Dashboard", type="secondary", use_container_width=True):
            st.info("Navigate to the Dashboard page to see detailed analysis.")


# Allow running as a Streamlit multipage without main app router
def _maybe_render_self():
    if st.runtime.exists():  # type: ignore[attr-defined]
        debug_write("🔍 **DEBUG:** Settings self-render called")
        render()


_maybe_render_self()