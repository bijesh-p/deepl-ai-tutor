"""Shared top-of-page back-navigation button used across frontend pages."""
from __future__ import annotations

import streamlit as st


def render_back_button(
    label: str,
    target_page: str,
    key: str,
    clear_keys: list[str] | None = None,
) -> None:
    """Render a small secondary "back" button that switches pages on click.

    clear_keys: session_state keys to drop before navigating (e.g. quiz/module
    state that shouldn't linger once the user leaves that flow).
    """
    if st.button(label, type="secondary", key=key):
        for k in clear_keys or []:
            st.session_state.pop(k, None)
        st.session_state["page"] = target_page
        st.rerun()
