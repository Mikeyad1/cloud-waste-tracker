"""
AWS credentials management component.
Handles session-only AWS credential configuration and validation.
"""

import streamlit as st
import os
from ..ui.beautiful_ui import (
    render_section_header, render_settings_card, close_settings_card,
    render_info_card, render_status_card, render_warning_card
)
from .settings_config import SettingsManager


def render_aws_credentials_section(settings_manager: SettingsManager) -> None:
    """Render the AWS credentials section with session-only management."""
    render_section_header("🔐 AWS Credentials (Session Only)")
    
    render_warning_card(
        "⚠️ Session-Only Credentials",
        "These credentials override environment variables only for this browser session. They are NOT saved to disk for security."
    )
    
    render_settings_card("AWS Credentials Configuration", "")
    
    cfg = settings_manager.load_settings()
    
    # Initialize session keys
    st.session_state.setdefault("aws_override_enabled", False)
    st.session_state.setdefault("aws_access_key_id", "")
    st.session_state.setdefault("aws_secret_access_key", "")
    st.session_state.setdefault("aws_default_region", os.getenv("AWS_DEFAULT_REGION", cfg.get("aws", {}).get("default_region", "us-east-1")))
    st.session_state.setdefault("aws_session_token", "")
    st.session_state.setdefault("aws_role_arn", "")
    st.session_state.setdefault("aws_external_id", "")
    st.session_state.setdefault("aws_role_session_name", "CloudWasteTracker")

    # Authentication method selection
    use_override = st.checkbox("🔑 Use these credentials for live scans (this session only)", value=st.session_state["aws_override_enabled"])
    
    current_auth_method = st.radio(
        "Authentication Method",
        options=["user", "role"],
        format_func=lambda x: "👤 IAM User (Access Key + Secret)" if x == "user" else "🏢 IAM Role (AssumeRole + External ID)",
        index=0 if st.session_state.get("aws_auth_method", "user") == "user" else 1,
        horizontal=True,
        key="aws_auth_method"
    )
    
    # Show appropriate fields based on auth method
    if current_auth_method == "user":
        render_user_credentials_form(use_override)
    else:
        render_role_credentials_form(use_override)
    
    close_settings_card()
    
    # Current Status Card
    render_status_card(current_auth_method, st.session_state.get("aws_override_enabled", False))


def render_user_credentials_form(use_override: bool) -> None:
    """Render IAM user credentials form."""
    render_info_card(
        "🔑 IAM User Credentials",
        "Provide your AWS Access Key and Secret Key for authentication."
    )
    
    with st.form("aws_user_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            ak = st.text_input("🔑 AWS Access Key ID", value="", placeholder="Enter your AWS Access Key ID", type="password")
            sk = st.text_input("🔐 AWS Secret Access Key", value="", placeholder="Enter your AWS Secret Access Key", type="password")
        
        with col2:
            stoken = st.text_input("🎫 AWS Session Token (optional)", value="", placeholder="Optional: For temporary credentials", type="password")
            rg = st.text_input("🌍 AWS Default Region", value="us-east-1", placeholder="us-east-1")
        
        submitted = st.form_submit_button("💾 Apply for this Session", type="primary", use_container_width=True)
        if submitted:
            st.session_state["aws_override_enabled"] = bool(use_override)
            st.session_state["aws_access_key_id"] = ak.strip()
            st.session_state["aws_secret_access_key"] = sk.strip()
            st.session_state["aws_session_token"] = stoken.strip()
            st.session_state["aws_default_region"] = rg.strip() or "us-east-1"
            
            if use_override and ak and sk:
                st.success("✅ AWS User credentials applied for this session!")
            elif use_override:
                st.warning("⚠️ Please provide both Access Key ID and Secret Access Key.")
            else:
                st.info("ℹ️ Credentials cleared. Using environment variables.")


def render_role_credentials_form(use_override: bool) -> None:
    """Render IAM role credentials form."""
    render_info_card(
        "🏢 IAM Role Credentials",
        "Use IAM Role assumption with External ID for enhanced security."
    )
    
    with st.form("aws_role_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            role_arn = st.text_input("🏢 Role ARN", value="", placeholder="arn:aws:iam::123456789012:role/YourRole")
            external_id = st.text_input("🔒 External ID", value="", placeholder="Optional external ID", type="password")
        
        with col2:
            session_name = st.text_input("📝 Session Name", value="CloudWasteTracker", placeholder="CloudWasteTracker")
            rg = st.text_input("🌍 AWS Default Region", value="us-east-1", placeholder="us-east-1")
        
        submitted = st.form_submit_button("💾 Apply for this Session", type="primary", use_container_width=True)
        if submitted:
            st.session_state["aws_override_enabled"] = bool(use_override)
            st.session_state["aws_role_arn"] = role_arn.strip()
            st.session_state["aws_external_id"] = external_id.strip()
            st.session_state["aws_role_session_name"] = session_name.strip() or "CloudWasteTracker"
            st.session_state["aws_default_region"] = rg.strip() or "us-east-1"
            
            if use_override and role_arn:
                st.success("✅ AWS Role credentials applied for this session!")
            elif use_override:
                st.warning("⚠️ Please provide a valid Role ARN.")
            else:
                st.info("ℹ️ Credentials cleared. Using environment variables.")
