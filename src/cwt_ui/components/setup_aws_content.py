# AWS setup content (used by Setup page). No page header.
from __future__ import annotations

import os
import streamlit as st

from cwt_ui.components.settings.settings_config import SettingsManager
from cwt_ui.components.settings.settings_aws import render_clean_credentials_form
from cwt_ui.components.services.scan_service import run_aws_scan


def _debug_write(message: str) -> None:
    pass


def _render_scan_mode_toggle() -> str:
    if "scan_mode" not in st.session_state:
        st.session_state["scan_mode"] = "regional"
    st.markdown("""
    <style>
        .scan-mode-container { display: flex; gap: 1rem; margin-bottom: 1.5rem; padding: 1rem; background-color: #f8f9fa; border-radius: 8px; align-items: center; }
        .scan-mode-option { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; padding: 0.5rem 1rem; border-radius: 20px; transition: all 0.3s ease; font-weight: 500; }
        .scan-mode-option:hover { background-color: #e9ecef; }
        .scan-mode-option.active { background-color: #1f77b4; color: white; }
    </style>
    """, unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("📍 Regional Scan", key="regional_scan_toggle", type="primary" if st.session_state["scan_mode"] == "regional" else "secondary", use_container_width=True):
            st.session_state["scan_mode"] = "regional"
            st.rerun()
    with col2:
        if st.button("🌍 Global Scan", key="global_scan_toggle", type="primary" if st.session_state["scan_mode"] == "global" else "secondary", use_container_width=True):
            st.session_state["scan_mode"] = "global"
            st.rerun()
    return st.session_state["scan_mode"]


def _group_regions_by_area(regions: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"USA": [], "Europe": [], "Asia Pacific": [], "Middle East": [], "Africa": [], "South America": [], "Canada": [], "Other": []}
    for region in regions:
        if any(region.startswith(p) for p in ["us-"]): groups["USA"].append(region)
        elif any(region.startswith(p) for p in ["eu-"]): groups["Europe"].append(region)
        elif any(region.startswith(p) for p in ["ap-", "ap-south"]): groups["Asia Pacific"].append(region)
        elif any(region.startswith(p) for p in ["me-"]): groups["Middle East"].append(region)
        elif any(region.startswith(p) for p in ["af-"]): groups["Africa"].append(region)
        elif any(region.startswith(p) for p in ["sa-"]): groups["South America"].append(region)
        elif any(region.startswith(p) for p in ["ca-"]): groups["Canada"].append(region)
        else: groups["Other"].append(region)
    return {k: sorted(v) for k, v in groups.items() if v}


def _render_region_selector() -> str | None:
    try:
        from core.services.region_service import discover_enabled_regions, get_region_display_name
        aws_credentials = None
        if st.session_state.get("aws_override_enabled"):
            aws_credentials = {"AWS_DEFAULT_REGION": st.session_state.get("aws_default_region", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))}
        try:
            available_regions = discover_enabled_regions(aws_credentials, st.session_state.get("aws_auth_method", "role"))
        except Exception:
            from core.services.region_service import _common_regions
            available_regions = _common_regions()
        if not available_regions:
            available_regions = ["us-east-1"]
        if "selected_region" not in st.session_state:
            st.session_state["selected_region"] = st.session_state.get("aws_default_region", "us-east-1")
        grouped = _group_regions_by_area(available_regions)
        region_options: dict[str, str | None] = {}
        ordered_options: list[str] = []
        for group_name in ["USA", "Canada", "Europe", "Asia Pacific", "Middle East", "Africa", "South America", "Other"]:
            if group_name not in grouped or not grouped[group_name]:
                continue
            ordered_options.append(f"━━━ {group_name} ━━━")
            region_options[f"━━━ {group_name} ━━━"] = None
            for region in grouped[group_name]:
                opt = f"  └─ {get_region_display_name(region)} ({region})"
                region_options[opt] = region
                ordered_options.append(opt)
        current_region = st.session_state["selected_region"]
        current_index = 0
        option_values = [v for v in region_options.values() if v is not None]
        for idx, opt in enumerate(ordered_options):
            if region_options.get(opt) == current_region:
                current_index = idx
                break
        selected_display = st.selectbox("📍 Select AWS Region", options=ordered_options, index=current_index, key="region_selector")
        if selected_display.startswith("━━━"):
            selected_region = current_region if current_region in option_values else (option_values[0] if option_values else "us-east-1")
            st.rerun()
        else:
            selected_region = region_options[selected_display]
        st.session_state["selected_region"] = selected_region
        return selected_region
    except Exception as e:
        st.error(f"❌ Error loading regions: {str(e)}")
        return "us-east-1"


def _render_clean_css() -> None:
    st.markdown("""
    <style>
        .main .block-container { padding-left: 2rem; padding-right: 2rem; padding-top: 2rem; padding-bottom: 2rem; max-width: 900px; }
        h2 { color: #1f77b4; margin-top: 1.5rem; margin-bottom: 0.5rem; }
        h3 { color: #495057; margin-top: 2rem; margin-bottom: 1rem; font-weight: 600; }
        .stButton > button { font-weight: 500; transition: all 0.2s ease; }
        .stButton > button:enabled:hover { transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
    </style>
    """, unsafe_allow_html=True)


def render_aws_setup_content() -> None:
    _render_clean_css()
    settings_manager = SettingsManager()
    cfg = settings_manager.load_settings()
    st.session_state.setdefault("aws_override_enabled", False)
    st.session_state.setdefault("aws_role_arn", "")
    st.session_state.setdefault("aws_external_id", "")
    st.session_state.setdefault("aws_default_region", os.getenv("AWS_DEFAULT_REGION", cfg.get("aws", {}).get("default_region", "us-east-1")))
    st.session_state.setdefault("aws_role_session_name", "CloudWasteTracker")
    st.session_state.setdefault("aws_auth_method", "role")
    st.session_state.setdefault("credentials_applied", False)
    st.markdown("### Step 1: Configure IAM Role")
    scan_mode = _render_scan_mode_toggle()
    if scan_mode == "global":
        st.info("💡 **Global Scan:** Your env vars will be used to assume the IAM role. The scan will discover and iterate all enabled AWS regions.")
    else:
        st.info("💡 **Regional Scan:** Scan a specific AWS region for faster results.")
    credentials_applied = render_clean_credentials_form(settings_manager)
    if st.session_state.get("_credentials_just_applied", False):
        st.session_state["credentials_applied"] = True
        st.session_state["_credentials_just_applied"] = False
        st.success("✅ **Role configured successfully!** Ready to test connection.")
    st.markdown("---")
    st.markdown("### Step 2: Test AWS Connection")
    has_credentials = st.session_state.get("credentials_applied", False) or st.session_state.get("aws_override_enabled", False)
    if has_credentials:
        status_text = "✅ **Role is configured.** Click below to scan." + (" Select a region for regional scan." if scan_mode == "regional" else "")
        status_bg, status_border, status_text_color = "#e7f5e7", "#28a745", "#155724"
    else:
        status_text = "⏳ **Configure your IAM Role in Step 1** to enable scanning."
        status_bg, status_border, status_text_color = "#f8f9fa", "#6c757d", "#495057"
    st.markdown(f"<div style='padding: 0.75rem 1rem; background-color: {status_bg}; border-left: 4px solid {status_border}; border-radius: 6px; margin-bottom: 1rem; color: {status_text_color};'>{status_text}</div>", unsafe_allow_html=True)
    selected_region = _render_region_selector() if scan_mode == "regional" else None
    if has_credentials:
        button_text = "🌍 Run Global Scan" if scan_mode == "global" else f"📍 Run Regional Scan ({selected_region})"
        scan_region = None if scan_mode == "global" else selected_region
        if st.button(button_text, type="primary", use_container_width=True):
            with st.spinner("Scanning..." if scan_mode == "regional" else "Scanning all enabled AWS regions..."):
                try:
                    ec2_df = run_aws_scan(region=scan_region)
                    if not ec2_df.empty:
                        st.success("✅ **Scan complete!** Found AWS resources.")
                        st.info(f"📊 Found {len(ec2_df)} EC2 instances.")
                        st.balloons()
                    else:
                        st.warning("⚠️ **Scan completed but no resources found.**")
                except Exception as e:
                    st.error(f"❌ **Scan failed:** {str(e)}")
                    st.exception(e)
    else:
        st.button("Run Scan", type="secondary", use_container_width=True, disabled=True)
    st.markdown("---")
    if st.session_state.get("last_scan_at"):
        st.markdown("### Ready to explore?")
        if st.button("📊 Go to Overview", type="secondary", use_container_width=True):
            st.info("💡 Use the sidebar to open **Overview** or **Optimization**.")
