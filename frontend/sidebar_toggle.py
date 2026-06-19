"""Custom always-visible sidebar collapse/expand toggle.

Streamlit's native sidebar control (`[data-testid="stSidebarCollapseButton"]`)
is `visibility:hidden` by default and never reliably becomes reachable via
hover in this Streamlit version (1.58.0) — a framework-level limitation, not
something fixable with CSS alone (see SPEC.md Open Questions, Phase 45/46).
This renders a small always-visible button in a `components.v1.html` iframe
that forwards its click to the real (hidden) native button via
`window.parent.document`, so the sidebar can always be toggled regardless of
whether the native control's hover-reveal works for a given browser/user.
"""
from __future__ import annotations

import streamlit as st


def render_sidebar_toggle() -> None:
    """Render the floating toggle. Call once per page, after set_page_config."""
    dark = bool(st.session_state.get("dark_mode", False))
    if dark:
        bg, bg_hover = "#6D28D9 0%, #4C1D95 100%", "#7C3AED 0%, #5B21B6 100%"
        shadow, shadow_hover = "rgba(109,40,217,0.45)", "rgba(124,58,237,0.55)"
    else:
        bg, bg_hover = "#4F46E5 0%, #2563EB 100%", "#4338CA 0%, #1D4ED8 100%"
        shadow, shadow_hover = "rgba(37,99,235,0.35)", "rgba(37,99,235,0.5)"

    st.iframe(
        f"""
        <html><body style="margin:0;padding:0;overflow:hidden;background:transparent;">
        <button id="ai-tutor-sb-toggle" title="Toggle sidebar" style="
            position:fixed; top:18px; left:0; width:18px; height:56px;
            background:linear-gradient(180deg,{bg}); border:none;
            border-radius:0 10px 10px 0; color:white; cursor:pointer; font-size:13px;
            display:flex; align-items:center; justify-content:center;
            box-shadow:3px 0 14px {shadow};
            transition:width 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
        ">&#8250;</button>
        <script>
          const btn = document.getElementById('ai-tutor-sb-toggle');
          btn.addEventListener('mouseenter', function() {{
            btn.style.width = '26px';
            btn.style.boxShadow = '4px 0 20px {shadow_hover}';
            btn.style.background = 'linear-gradient(180deg,{bg_hover})';
          }});
          btn.addEventListener('mouseleave', function() {{
            btn.style.width = '18px';
            btn.style.boxShadow = '3px 0 14px {shadow}';
            btn.style.background = 'linear-gradient(180deg,{bg})';
          }});
          btn.addEventListener('click', function() {{
            try {{
              const native = window.parent.document.querySelector(
                '[data-testid="stSidebarCollapseButton"] button'
              );
              if (native) native.click();
            }} catch (e) {{}}
          }});
        </script>
        </body></html>
        """,
        height=80,
    )
