from __future__ import annotations

import streamlit as st

from .shared_css import load_beautiful_css


def render_page_header(title: str, subtitle: str | None = None, icon: str | None = None) -> None:
    """
    Render a standardized gradient header consistent across all pages.

    Args:
        title: Main heading text.
        subtitle: Optional secondary line of text below the title.
        icon: Optional emoji/icon prefix for the title.
    """
    load_beautiful_css()

    heading = f"{icon} {title}" if icon else title
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""

    st.markdown(
        f"""
        <div class="beautiful-header">
            <h1>{heading}</h1>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

