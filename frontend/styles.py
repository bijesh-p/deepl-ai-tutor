"""Global CSS injection and reusable HTML component helpers for the AI Tutor UI."""
from __future__ import annotations

import streamlit as st

_GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── AI Tutor — Global Styles ─────────────────────────────────────────── */

/* Apply Inter to text content only.
   Deliberately excludes bare `button`, `span`, and `.element-container button` so that:
   - Streamlit's sidebar-collapse button (Material Symbols: keyboard_double_arrow_right)
   - st.expander toggle arrow (Material Symbols: expand_more / keyboard_arrow_right)
   keep their glyph font and do NOT render as raw "_arrow" text.
   Only .stButton button (user-created via st.button()) gets Inter. */
html, body, .stApp, .main, .block-container,
input, select, textarea, p, label,
.stMarkdown, .stCaption, .stText,
.stButton button {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}

/* Page layout — compact top padding so content starts near the top,
   sensible side padding so text isn't jammed against the edge on narrow screens */
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 960px !important;
}
/* Mobile: drop side padding further */
@media (max-width: 640px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-top: 0.25rem !important;
    }
}

/* ── Typography ────────────────────────────────────────────────────────── */
/* Reset browser default top-margins on headings — they add large invisible gaps
   at the top of every page section */
h1, h2, h3, h4 { margin-top: 0 !important; margin-bottom: 0.4rem !important; }
h1 { font-weight: 700 !important; letter-spacing: -0.025em !important; }
h2 { font-weight: 600 !important; letter-spacing: -0.015em !important; }
h3 { font-weight: 600 !important; letter-spacing: -0.01em !important; }
p  { font-weight: 400 !important; line-height: 1.6 !important; }

/* ── Buttons ───────────────────────────────────────────────────────────── */
.stButton button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
    padding: 0.4rem 1rem !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    min-width: 0 !important;
}
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
    border: none !important;
    color: white !important;
    box-shadow: 0 1px 3px rgba(37,99,235,0.3) !important;
}
.stButton button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.4) !important;
    transform: translateY(-1px) !important;
}
.stButton button[kind="secondary"]:hover {
    border-color: #2563EB !important;
    color: #2563EB !important;
    background: #EFF6FF !important;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────
 * Palette — soft indigo-lavender gradient, white main area blend
 *   Sidebar bg : #EEF2FF → #F5F0FF  (indigo-50 → purple-50 gradient)
 *   Border     : #C7D2FE  (indigo-200)
 *   Primary txt: #1E1B4B  contrast 13:1 on bg  ✓ WCAG AAA
 *   Secondary  : #4B5563  contrast  7:1         ✓ WCAG AA
 *   Label hint : #818CF8  contrast  3.5:1       (9px decorative, uppercase)
 *   Font       : Inter — clean, modern, web-standard
 *
 * Collapsible: uses Streamlit's own native collapse control, which is
 * `visibility:hidden` by default and unreliable to reach via hover in this
 * Streamlit version (1.58.0) — see SPEC.md Open Questions, Phase 45/46/47.
 * `frontend/sidebar_toggle.py::render_sidebar_toggle()` renders a small
 * always-visible custom button (via `st.iframe()`) that forwards clicks to
 * the real hidden control; the rule below just pins that iframe
 * (`[data-testid="stIFrame"]`) to a fixed spot on the page edge.
 * Do NOT override transform on the sidebar itself — that breaks the
 * slide-in/out animation.
 */
[data-testid="stIFrame"] {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 30px !important;
    height: 80px !important;
    z-index: 999999 !important;
    border: none !important;
    background: transparent !important;
}

[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(170deg, #EEF2FF 0%, #F5F0FF 100%) !important;
    border-right: 1px solid #C7D2FE !important;
    padding: 0.65rem 0.8rem 1rem !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

/* Apply Inter to sidebar TEXT nodes only.
   The broad [data-testid="stSidebar"] * selector was removed because it
   overwrites the Material Symbols font on the sidebar collapse/expand icon,
   making the glyph render as raw text and the button become unclickable. */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .element-container {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}


/* Base text */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stCaption {
    color: #374151 !important;
    font-size: 12px !important;
    font-weight: 400 !important;
}

/* Section labels — <div class="sb-label">Navigate</div> */
[data-testid="stSidebar"] .sb-label {
    font-size: 9px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.11em !important;
    color: #818CF8 !important;
    padding: 11px 0 3px !important;
    border-top: 1px solid #C7D2FE !important;
    margin-top: 4px !important;
    line-height: 1 !important;
}

/* Selectboxes — white pill on the tinted bg */
[data-testid="stSidebar"] .stSelectbox { margin-bottom: 4px !important; }
[data-testid="stSidebar"] .stSelectbox label { font-size: 11px !important; color: #6366F1 !important; font-weight: 500 !important; }
[data-testid="stSidebar"] .stSelectbox > div > div {
    min-height: 30px !important;
    padding: 3px 10px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    border: 1px solid #C7D2FE !important;
    background: #FFFFFF !important;
    color: #1E1B4B !important;
    box-shadow: 0 1px 2px rgba(99,102,241,0.06) !important;
}

/* Toggles */
[data-testid="stSidebar"] .stToggle { padding: 1px 0 !important; margin-bottom: 2px !important; }
[data-testid="stSidebar"] .stToggle label,
[data-testid="stSidebar"] .stToggle p {
    font-size: 12px !important;
    font-weight: 500 !important;
    color: #374151 !important;
}

/* ── Sidebar buttons — scoped to .element-container so Streamlit's own
   internal controls (sidebar toggle with keyboard_double_arrow_right icon)
   are NOT affected (those live outside .element-container). ── */
[data-testid="stSidebar"] .element-container .stButton button {
    background: rgba(255,255,255,0.65) !important;
    border: 1px solid #C7D2FE !important;
    color: #3730A3 !important;
    width: 100% !important;
    text-align: left !important;
    padding: 5px 11px !important;
    min-height: 32px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    border-radius: 8px !important;
    margin-bottom: 3px !important;
    box-shadow: 0 1px 2px rgba(99,102,241,0.07) !important;
    letter-spacing: 0 !important;
    backdrop-filter: blur(4px) !important;
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
[data-testid="stSidebar"] .element-container .stButton button:hover {
    background: #E0E7FF !important;
    border-color: #818CF8 !important;
    color: #312E81 !important;
    box-shadow: 0 2px 6px rgba(99,102,241,0.18) !important;
    transform: none !important;
}

/* Sign-out — rose tint.
   A .sb-signout-marker <span> is rendered immediately before the sign-out button via st.markdown().
   :has() lets us select the element-container that follows the marker's container. */
[data-testid="stSidebar"] .element-container:has(.sb-signout-marker) + .element-container .stButton button {
    background: rgba(255,241,241,0.85) !important;
    border: 1px solid #FECACA !important;
    color: #DC2626 !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-align: center !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .element-container:has(.sb-signout-marker) + .element-container .stButton button:hover {
    background: #FEF2F2 !important;
    border-color: #F87171 !important;
    color: #B91C1C !important;
    box-shadow: 0 1px 4px rgba(220,38,38,0.15) !important;
}

/* Hide native hr — sb-label border-top is the divider */
[data-testid="stSidebar"] hr { display: none !important; }


/* Tighten element gaps */
[data-testid="stSidebar"] .element-container { margin-bottom: 0 !important; }
[data-testid="stSidebar"] .stMarkdown { margin-bottom: 0 !important; }

/* ── Progress bar ──────────────────────────────────────────────────────── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #2563EB 0%, #7C3AED 100%) !important;
    border-radius: 999px !important;
}

/* ── Metrics ────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #EFF6FF 0%, #F5F3FF 100%) !important;
    border: 1px solid #BFDBFE !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
}
[data-testid="stMetricValue"] { color: #1D4ED8 !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #3730A3 !important; font-weight: 600 !important; font-size: 0.85rem !important; }

/* ── Alert boxes ────────────────────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: 10px !important; }

/* ── Expanders ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary { font-weight: 500 !important; padding: 0.75rem 1rem !important; }

/* ── Tabs ───────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0 !important;
    font-weight: 500 !important;
    padding: 0.5rem 1.25rem !important;
}
.stTabs [aria-selected="true"] { color: #2563EB !important; }

/* ── Forms ──────────────────────────────────────────────────────────────── */
[data-testid="stForm"] {
    border-radius: 12px !important;
    border: 1px solid #E5E7EB !important;
    background: #FAFAFA !important;
}

/* ── File uploader ──────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border-radius: 10px !important;
}

/* ── Toggle ─────────────────────────────────────────────────────────────── */
[data-testid="stToggle"] label { font-weight: 500 !important; }

/* ── Quiz option cards — radio & checkbox as full-width clickable cards ─── */

/* Counter for A / B / C / D letter badges.
   max-width keeps options aligned with question text on wide screens. */
[data-testid="stRadio"] [role="radiogroup"] {
    counter-reset: quiz-opt !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 8px !important;
    max-width: 680px !important;
    width: 100% !important;
}
[data-testid="stCheckbox"] {
    counter-reset: none !important;
}

/* Each radio label → card.
   Scoped to [role="radiogroup"] > label (direct children only) so the
   widget-level <label> outside the group is never counted. */
[data-testid="stRadio"] [role="radiogroup"] > label {
    counter-increment: quiz-opt !important;
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 14px 18px 14px 14px !important;
    border: 2px solid #E5E7EB !important;
    border-radius: 12px !important;
    background: #FFFFFF !important;
    cursor: pointer !important;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease !important;
    box-sizing: border-box !important;
    margin-bottom: 0 !important;
    position: relative !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:hover {
    border-color: #93C5FD !important;
    background: #F0F8FF !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
    border-color: #2563EB !important;
    background: #EFF6FF !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}

/* Letter badge A B C D E via ::before */
[data-testid="stRadio"] [role="radiogroup"] > label::before {
    content: counter(quiz-opt, upper-alpha) !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: 28px !important;
    height: 28px !important;
    border-radius: 50% !important;
    background: #F3F4F6 !important;
    color: #6B7280 !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    margin-right: 14px !important;
    flex-shrink: 0 !important;
    font-family: 'Inter', sans-serif !important;
    transition: background 0.15s ease, color 0.15s ease !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:hover::before {
    background: #DBEAFE !important;
    color: #1D4ED8 !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked)::before {
    background: #2563EB !important;
    color: #FFFFFF !important;
}

/* Bigger, clearer option text */
[data-testid="stRadio"] [role="radiogroup"] > label p,
[data-testid="stRadio"] [role="radiogroup"] > label div {
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #1F2937 !important;
    line-height: 1.5 !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p,
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) div {
    color: #1E40AF !important;
    font-weight: 600 !important;
}

/* Hide Streamlit's default radio indicator dot (we use ::before badge) */
[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child {
    display: none !important;
}

/* Each checkbox label → card */
[data-testid="stCheckbox"] label {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 14px 18px !important;
    border: 2px solid #E5E7EB !important;
    border-radius: 12px !important;
    background: #FFFFFF !important;
    cursor: pointer !important;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease !important;
    box-sizing: border-box !important;
    margin-bottom: 8px !important;
    gap: 12px !important;
}
[data-testid="stCheckbox"] label:hover {
    border-color: #93C5FD !important;
    background: #F0F8FF !important;
}
[data-testid="stCheckbox"] label:has(input:checked) {
    border-color: #2563EB !important;
    background: #EFF6FF !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}
[data-testid="stCheckbox"] label p,
[data-testid="stCheckbox"] label span {
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #1F2937 !important;
    line-height: 1.5 !important;
}
[data-testid="stCheckbox"] label:has(input:checked) p,
[data-testid="stCheckbox"] label:has(input:checked) span {
    color: #1E40AF !important;
    font-weight: 600 !important;
}

/* ── Hide Streamlit dev-mode chrome (Rerun / Always rerun / file-change) ─── */
#MainMenu                         { visibility: hidden !important; }
[data-testid="stToolbar"]         { display: none !important; }
[data-testid="stDecoration"]      { display: none !important; }
[data-testid="stStatusWidget"]    { display: none !important; }
.stAppToolbar                     { display: none !important; }
[data-testid="stAppToolbar"]      { display: none !important; }

/* ── Keyframe animations ─────────────────────────────────────────────────── */
@keyframes ai-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.55; transform: scale(0.93); }
}
@keyframes ai-glow {
  0%, 100% { box-shadow: 0 0 0 0   rgba(37,99,235,0.45); }
  50%       { box-shadow: 0 0 0 8px rgba(37,99,235,0);    }
}
@keyframes ai-spin {
  to { transform: rotate(360deg); }
}
@keyframes ai-bounce {
  0%, 80%, 100% { transform: translateY(0);   opacity: 0.25; }
  40%           { transform: translateY(-7px); opacity: 1;    }
}
@keyframes ai-shimmer {
  0%   { background-position: -600px 0; }
  100% { background-position:  600px 0; }
}
@keyframes ai-slide-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0);   }
}
@keyframes ai-wave-bar {
  0%, 100% { transform: scaleY(0.35); opacity: 0.5; }
  50%       { transform: scaleY(1);    opacity: 1;   }
}
@keyframes ai-stripes {
  0%   { background-position: 0     0; }
  100% { background-position: 40px  0; }
}
</style>
"""


# ── Dark mode ────────────────────────────────────────────────────────────────
# Streamlit's own [theme] in .streamlit/config.toml is process-wide and can't be
# switched per user at runtime (one shared server, many users), so dark mode is
# implemented entirely as an extra stylesheet appended after _GLOBAL_CSS — it wins
# by source order, no !important escalation needed against Streamlit's own CSS.
# Custom HTML cards (the helper functions below) keep their explicit light inline
# colors and simply float on the dark canvas — a deliberate "light card on dark
# page" choice, not an oversight; see plan.md Phase 41/44.

_DARK_PALETTE: dict[str, str] = {
    "app_bg": "#0F1117",
    "text_primary": "#F1F5F9",      # vs app_bg: ~15:1 contrast, WCAG AAA
    "text_secondary": "#94A3B8",    # vs app_bg: ~7:1 contrast, WCAG AA
    "sidebar_grad_start": "#1E293B",   # slate-800 — neutral, soothing gray
    "sidebar_grad_end": "#0F172A",     # slate-900, blends into app_bg
    "sidebar_border": "#475569",       # slate-600
    "sidebar_text": "#CBD5E1",      # vs sidebar bg: ~9:1 contrast, WCAG AAA
    "card_bg": "#1A1D29",
    "card_border": "#2D2F3D",
    "metric_grad_start": "#1E2536",
    "metric_grad_end": "#241F38",
    "metric_border": "#3730A3",
    "form_bg": "#161821",
}

# New accent for the colorful-yet-soothing refresh (Phase 41/44) — used sparingly
# for variety beyond the primary blue/purple (e.g. concept-rail mastery chips).
ACCENT_TEAL = "#14B8A6"


def _theme_overrides_css(dark: bool) -> str:
    """Background/text overrides applied on top of _GLOBAL_CSS when dark mode is on."""
    if not dark:
        return ""
    p = _DARK_PALETTE
    return f"""
<style>
/* Root containers — color cascades to plain text via inheritance; anything with
   its own inline color (our HTML helper cards) is untouched by inheritance. */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] {{
    background: {p['app_bg']} !important;
    color: {p['text_primary']} !important;
}}

[data-testid="stCaptionContainer"] {{ color: {p['text_secondary']} !important; }}

[data-testid="stSidebar"] > div:first-child {{
    background: linear-gradient(170deg, {p['sidebar_grad_start']} 0%, {p['sidebar_grad_end']} 100%) !important;
    border-right: 1px solid {p['sidebar_border']} !important;
}}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stCaption {{
    color: {p['sidebar_text']} !important;
}}
[data-testid="stSidebar"] .sb-label {{ color: {p['text_secondary']} !important; border-top-color: {p['sidebar_border']} !important; }}
/* Sign-out button's label text sits in a nested <p>, which the generic sidebar
   text rule above matches directly (and direct rules always beat inherited
   ones) — washing out the button's own dark-red text on its light rose card.
   Out-specify it, same pattern as the checkbox-label fix below. */
[data-testid="stSidebar"] .element-container:has(.sb-signout-marker) + .element-container .stButton button p {{
    color: #B91C1C !important;
}}
/* Checked toggle/checkbox labels get an extra Streamlit-internal blue tint with
   higher specificity than the generic sidebar text rule above — out-specify it. */
[data-testid="stSidebar"] [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p {{
    color: {p['sidebar_text']} !important;
}}
[data-testid="stSidebar"] .stSelectbox > div > div {{
    background: {p['card_bg']} !important;
    border-color: {p['sidebar_border']} !important;
    color: {p['text_primary']} !important;
}}
[data-testid="stSidebar"] .element-container .stButton button {{
    background: rgba(255,255,255,0.06) !important;
    border-color: {p['sidebar_border']} !important;
    color: {p['sidebar_text']} !important;
}}
[data-testid="stSidebar"] .element-container .stButton button:hover {{
    background: rgba(255,255,255,0.12) !important;
}}

/* Secondary buttons (the default st.button() kind) only ever had a :hover rule
   in _GLOBAL_CSS — no resting-state color — so they fell back to Streamlit's
   own light-theme text color, invisible against the dark page until hovered.
   Low specificity here so the more-specific sidebar-button rule above, and the
   sign-out button's own rule, both continue to win in their own contexts. */
.stButton button[kind="secondary"] {{
    background: {p['card_bg']} !important;
    border-color: #475569 !important;
    color: {p['text_primary']} !important;
}}

[data-testid="stMetric"] {{
    background: linear-gradient(135deg, {p['metric_grad_start']} 0%, {p['metric_grad_end']} 100%) !important;
    border-color: {p['metric_border']} !important;
}}
[data-testid="stMetricValue"] {{ color: #93C5FD !important; }}
[data-testid="stMetricLabel"] {{ color: #A5B4FC !important; }}

[data-testid="stExpander"] {{ background: {p['card_bg']} !important; border-color: {p['card_border']} !important; }}
/* The expander's <summary> (clickable header) keeps Streamlit's own native
   near-white background regardless of the outer dark background above it —
   white text (inherited from .stApp) on that native background is white on
   white. */
[data-testid="stExpander"] summary {{ background: {p['card_bg']} !important; }}
[data-testid="stForm"] {{ background: {p['form_bg']} !important; border-color: {p['card_border']} !important; }}
[data-testid="stFileUploader"] section {{ background: {p['form_bg']} !important; border-color: {p['card_border']} !important; }}
[data-testid="stFileUploaderDropzoneInstructions"] span,
[data-testid="stFileUploaderDropzoneInstructions"] small {{ color: {p['text_secondary']} !important; }}
/* The uploader's own "Browse files" button isn't wrapped in .stButton, so the
   .stButton button[kind="secondary"] rule above never reaches it — it fell
   back to inheriting the page-wide dark text color on top of Streamlit's
   native white button background (white-on-white). */
[data-testid="stFileUploader"] button[kind="secondary"] {{
    background: {p['card_bg']} !important;
    border-color: #475569 !important;
    color: {p['text_primary']} !important;
}}

/* Quiz option cards — base (unchecked) state. */
[data-testid="stRadio"] [role="radiogroup"] > label,
[data-testid="stCheckbox"] label {{
    background: {p['card_bg']} !important;
    border-color: {p['card_border']} !important;
}}
[data-testid="stRadio"] [role="radiogroup"] > label p,
[data-testid="stRadio"] [role="radiogroup"] > label div,
[data-testid="stCheckbox"] label p,
[data-testid="stCheckbox"] label span {{
    color: {p['text_primary']} !important;
}}

/* Quiz option cards — hover/checked. _GLOBAL_CSS's hover (#F0F8FF) and
   checked (#EFF6FF) backgrounds are unconditional, near-white "light card"
   colors meant for the light theme — combined with the near-white base text
   color above, that left hover/checked text invisible (near-white on
   near-white) in dark mode. Override with dark-appropriate equivalents;
   ordered after :hover so :has(input:checked) wins when both apply. */
[data-testid="stRadio"] [role="radiogroup"] > label:hover,
[data-testid="stCheckbox"] label:hover {{
    background: #233047 !important;
    border-color: #60A5FA !important;
}}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked),
[data-testid="stCheckbox"] label:has(input:checked) {{
    background: #1E3A5F !important;
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.25) !important;
}}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p,
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) div,
[data-testid="stCheckbox"] label:has(input:checked) p,
[data-testid="stCheckbox"] label:has(input:checked) span {{
    color: #BFDBFE !important;
    font-weight: 600 !important;
}}

/* Tabs (module_viewer topic tabs) — _GLOBAL_CSS only colors the *selected*
   tab (blue); unselected tabs use Streamlit's light-theme default text color
   (#111827), invisible against the dark page until selected. */
.stTabs [data-baseweb="tab"] {{ color: {p['text_secondary']} !important; }}
.stTabs [aria-selected="true"] {{ color: #60A5FA !important; }}
</style>
"""


def inject_global_css() -> None:
    """Inject global CSS, then dark-mode overrides if enabled for this session.

    Call once at the top of app.py after set_page_config.
    """
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)
    overrides = _theme_overrides_css(bool(st.session_state.get("dark_mode", False)))
    if overrides:
        st.markdown(overrides, unsafe_allow_html=True)


# ── Reusable HTML components ────────────────────────────────────────────────

_STEP_COLORS = {
    "done":    ("background:#10B981;color:white;", "color:#047857;font-weight:600;", "#10B981"),
    "active":  ("background:#2563EB;color:white;box-shadow:0 0 0 4px rgba(37,99,235,0.2);", "color:#1E40AF;font-weight:700;", "#2563EB"),
    "pending": ("background:#E5E7EB;color:#9CA3AF;", "color:#9CA3AF;", "#E5E7EB"),
}


def step_progress_html(steps: list[str], current_idx: int) -> str:
    """Horizontal step-progress bar. Active step pulses with glow animation."""
    n = len(steps)
    parts: list[str] = []

    for i, label in enumerate(steps):
        if i < current_idx or current_idx == -1:
            key = "done"
            icon = "✓"
        elif i == current_idx:
            key = "active"
            icon = "●"
        else:
            key = "pending"
            icon = str(i + 1)

        dot_s, lbl_s, _ = _STEP_COLORS[key]
        anim = "animation:ai-pulse 1.6s ease-in-out infinite,ai-glow 1.6s ease-in-out infinite;" if key == "active" else ""

        step_html = (
            f'<div style="display:flex;flex-direction:column;align-items:center;flex:1;min-width:55px;">'
            f'<div style="width:28px;height:28px;border-radius:50%;{dot_s}{anim}'
            f'display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;margin-bottom:5px;">'
            f'{icon}</div>'
            f'<div style="font-size:10.5px;text-align:center;{lbl_s}line-height:1.3;">{label}</div>'
            f'</div>'
        )
        parts.append(step_html)

        if i < n - 1:
            is_done_bar = i + 1 <= current_idx or current_idx == -1
            bar_bg = "#10B981" if is_done_bar else "#E5E7EB"
            # Animate the bar that feeds into the active step
            bar_anim = ""
            if i + 1 == current_idx:
                bar_anim = (
                    "background:linear-gradient(90deg,#10B981 0%,#2563EB 50%,#E5E7EB 100%);"
                    "background-size:200% 100%;animation:ai-shimmer 2s linear infinite;"
                )
            bar_style = bar_anim if bar_anim else f"background:{bar_bg};"
            parts.append(
                f'<div style="flex:1;height:2px;{bar_style}margin:0 4px;margin-top:-19px;border-radius:2px;"></div>'
            )

    inner = "".join(parts)
    return (
        f'<div style="display:flex;align-items:flex-start;padding:0.9rem 1.25rem 1rem;'
        f'background:#F8FAFC;border-radius:12px;border:1px solid #E2E8F0;margin-bottom:1rem;">'
        f'{inner}</div>'
    )


def module_card_html(title: str, source: str, date_label: str, is_published: bool = False) -> str:
    """Info section of a module card (title + meta). Actions are Streamlit buttons rendered below."""
    pub = ('<span style="display:inline-block;background:#D1FAE5;color:#065F46;font-size:10px;'
           'padding:2px 8px;border-radius:999px;font-weight:600;margin-left:8px;">Published</span>'
           if is_published else "")
    # Published (shared-library) modules get the teal accent instead of the
    # primary blue, so the "My Modules" and "Shared Library" lists are
    # distinguishable from each other at a glance.
    accent = ACCENT_TEAL if is_published else "#2563EB"
    return f"""<div style="padding:14px 18px;background:white;border:1px solid #E5E7EB;border-left:4px solid {accent};border-radius:10px;margin-bottom:6px;">
  <div style="font-weight:600;font-size:15px;color:#111827;margin-bottom:5px;">{title}{pub}</div>
  <div style="font-size:12px;color:#6B7280;">{source}</div>
  <div style="font-size:11px;color:#9CA3AF;margin-top:3px;">{date_label}</div>
</div>"""


def score_banner_html(score: int, total: int, pct: float) -> str:
    """Large score display for the quiz results page."""
    if pct >= 95:
        # Teal tier for a (near-)perfect score — a distinct celebratory accent
        # rather than just a brighter green, used sparingly per the Phase 41/44
        # color refresh.
        fg, bg, border, grade = "#0F766E", "#F0FDFA", "#99F6E4", "Perfect!"
        ring = ACCENT_TEAL
    elif pct >= 70:
        fg, bg, border, grade = "#065F46", "#F0FDF4", "#A7F3D0", "Excellent!" if pct >= 90 else "Well done!"
        ring = "#10B981"
    elif pct >= 50:
        fg, bg, border, grade = "#92400E", "#FFFBEB", "#FDE68A", "Keep practicing!"
        ring = "#F59E0B"
    else:
        fg, bg, border, grade = "#991B1B", "#FEF2F2", "#FECACA", "Needs more study"
        ring = "#EF4444"

    return f"""<div style="text-align:center;padding:2.5rem 2rem;background:{bg};border:2px solid {border};border-radius:20px;margin:0.75rem 0 1.5rem;">
  <div style="display:inline-flex;align-items:center;justify-content:center;width:110px;height:110px;border-radius:50%;border:6px solid {ring};background:white;margin-bottom:1rem;">
    <div style="font-size:2.25rem;font-weight:800;color:{fg};line-height:1;">{pct:.0f}<span style="font-size:1.1rem;">%</span></div>
  </div>
  <div style="font-size:1.3rem;font-weight:700;color:{fg};margin-bottom:4px;">{grade}</div>
  <div style="font-size:0.95rem;color:#6B7280;">{score} of {total} questions correct</div>
</div>"""


def question_card_html(number: int, text: str, q_type: str) -> str:
    """Decorative card header for a quiz question."""
    badge_color = "#DBEAFE" if q_type == "single_choice" else "#EDE9FE"
    badge_text_color = "#1E40AF" if q_type == "single_choice" else "#5B21B6"
    badge_label = "Single choice" if q_type == "single_choice" else "Multi choice"
    return f"""<div style="padding:14px 18px 10px;background:white;border:1px solid #E5E7EB;border-radius:10px;margin-bottom:-8px;border-bottom:none;border-bottom-left-radius:0;border-bottom-right-radius:0;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
    <div style="min-width:26px;height:26px;border-radius:50%;background:#2563EB;color:white;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;">{number}</div>
    <div style="font-weight:600;font-size:14px;color:#111827;flex:1;">{text}</div>
    <span style="background:{badge_color};color:{badge_text_color};font-size:10px;padding:2px 8px;border-radius:999px;font-weight:600;white-space:nowrap;">{badge_label}</span>
  </div>
</div>"""


def page_header_html(title: str, subtitle: str = "", icon: str = "") -> str:
    """Branded page header banner."""
    icon_html = f'<div style="font-size:2rem;margin-bottom:0.4rem;">{icon}</div>' if icon else ""
    sub_html = f'<div style="font-size:0.95rem;color:#6B7280;margin-top:4px;">{subtitle}</div>' if subtitle else ""
    # Slim three-color accent bar on top of the banner — ties the primary blue,
    # the new teal accent, and the existing purple accent together on the
    # page's most visible card, without changing its light palette.
    accent_bar = (
        f'<div style="height:3px;border-radius:14px 14px 0 0;'
        f'background:linear-gradient(90deg,#2563EB 0%,{ACCENT_TEAL} 50%,#7C3AED 100%);"></div>'
    )
    return (
        f'<div style="border-radius:14px;border:1px solid #DBEAFE;margin-bottom:1.5rem;overflow:hidden;">'
        f'{accent_bar}'
        f'<div style="padding:1.5rem 2rem;background:linear-gradient(135deg,#EFF6FF 0%,#F5F3FF 100%);">'
        f'{icon_html}'
        f'<h1 style="margin:0;font-size:1.6rem;font-weight:800;color:#1E1B4B;">{title}</h1>'
        f'{sub_html}</div></div>'
    )


# ── Animated pipeline status components ────────────────────────────────────

def bouncing_dots_html() -> str:
    """Three bouncing dots — used inline to show active LLM work."""
    d = "width:8px;height:8px;border-radius:50%;background:#2563EB;display:inline-block;"
    delays = ["0s", "0.18s", "0.36s"]
    dots = "".join(
        f'<span style="{d}animation:ai-bounce 1.1s ease-in-out {dl} infinite;"></span>'
        for dl in delays
    )
    return f'<span style="display:inline-flex;gap:4px;align-items:center;vertical-align:middle;">{dots}</span>'


def parsing_status_html(detail: str, elapsed: int) -> str:
    """Animated document-scan card for the parsing stage."""
    elapsed_str = f"{elapsed}s" if elapsed > 0 else "starting…"
    return (
        '<div style="padding:18px 20px;background:#EFF6FF;border:1px solid #BFDBFE;'
        'border-radius:12px;display:flex;align-items:center;gap:16px;">'

        # Spinning doc icon
        '<div style="flex-shrink:0;width:42px;height:42px;border-radius:50%;'
        'background:#2563EB;display:flex;align-items:center;justify-content:center;">'
        '<div style="font-size:20px;animation:ai-spin 2s linear infinite;">🔍</div>'
        '</div>'

        # Text
        '<div style="flex:1;">'
        f'<div style="font-weight:600;color:#1E40AF;font-size:14px;margin-bottom:3px;">{detail}</div>'
        f'<div style="font-size:12px;color:#3B82F6;">Elapsed: {elapsed_str}</div>'
        '</div>'

        # Animated scan bars
        '<div style="display:flex;gap:3px;align-items:flex-end;height:28px;flex-shrink:0;">'
        + "".join(
            f'<div style="width:4px;border-radius:2px;background:#93C5FD;'
            f'animation:ai-wave-bar 1s ease-in-out {0.1*i:.1f}s infinite;"></div>'
            for i in range(6)
        )
        + '</div></div>'
    )


def slide_chips_html(enriched_topics: list, current_topic: str, total_topics: int) -> str:
    """Row of slide chips: green for done, pulsing blue for current, grey for pending."""
    if not enriched_topics and not current_topic:
        return ""

    chips: list[str] = []

    # Completed slides
    for et in enriched_topics:
        title = getattr(getattr(et, "topic", None), "title", str(et))
        short = (title[:22] + "…") if len(title) > 22 else title
        chips.append(
            f'<div style="display:inline-flex;align-items:center;gap:5px;'
            f'padding:4px 10px;background:#D1FAE5;border:1px solid #6EE7B7;'
            f'border-radius:999px;font-size:11px;color:#065F46;font-weight:500;'
            f'animation:ai-slide-in 0.35s ease-out;">'
            f'<span style="font-size:10px;">✓</span>{short}</div>'
        )

    # Currently generating
    if current_topic:
        short = (current_topic[:22] + "…") if len(current_topic) > 22 else current_topic
        chips.append(
            f'<div style="display:inline-flex;align-items:center;gap:6px;'
            f'padding:4px 12px;background:#DBEAFE;border:1px solid #93C5FD;'
            f'border-radius:999px;font-size:11px;color:#1E40AF;font-weight:600;'
            f'animation:ai-pulse 1.4s ease-in-out infinite;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:#2563EB;'
            f'animation:ai-pulse 0.9s ease-in-out infinite;display:inline-block;"></span>'
            f'{short}…</div>'
        )

    inner = "\n".join(chips)
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 14px;">'
        f'{inner}</div>'
    )


def concept_rail_html(mastered: list[str], current: str, remaining: list[str]) -> str:
    """Row of concept chips for the adaptive tutor: green for mastered, pulsing
    blue for the current concept, grey for ones not yet reached — gives a clear
    "where am I" indicator across the whole module, in canonical topic order.
    """
    if not mastered and not current and not remaining:
        return ""

    chips: list[str] = []

    for title in mastered:
        short = (title[:22] + "…") if len(title) > 22 else title
        chips.append(
            f'<div style="display:inline-flex;align-items:center;gap:5px;'
            f'padding:4px 10px;background:#D1FAE5;border:1px solid #6EE7B7;'
            f'border-radius:999px;font-size:11px;color:#065F46;font-weight:500;">'
            f'<span style="font-size:10px;">✓</span>{short}</div>'
        )

    if current:
        short = (current[:22] + "…") if len(current) > 22 else current
        chips.append(
            f'<div style="display:inline-flex;align-items:center;gap:6px;'
            f'padding:4px 12px;background:#DBEAFE;border:1px solid #93C5FD;'
            f'border-radius:999px;font-size:11px;color:#1E40AF;font-weight:600;'
            f'animation:ai-pulse 1.4s ease-in-out infinite;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:#2563EB;'
            f'animation:ai-pulse 0.9s ease-in-out infinite;display:inline-block;"></span>'
            f'{short}</div>'
        )

    for title in remaining:
        short = (title[:22] + "…") if len(title) > 22 else title
        chips.append(
            f'<div style="display:inline-flex;align-items:center;gap:5px;'
            f'padding:4px 10px;background:#F3F4F6;border:1px solid #E5E7EB;'
            f'border-radius:999px;font-size:11px;color:#9CA3AF;font-weight:500;">'
            f'{short}</div>'
        )

    inner = "\n".join(chips)
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 14px;">'
        f'{inner}</div>'
    )


def skeleton_slide_html(label: str = "Generating slide content…") -> str:
    """Shimmering skeleton card indicating an LLM call is in flight."""
    shimmer = (
        "background:linear-gradient(90deg,#F3F4F6 25%,#E5E7EB 50%,#F3F4F6 75%);"
        "background-size:600px 100%;animation:ai-shimmer 1.6s linear infinite;"
    )
    return (
        f'<div style="padding:16px 18px;border:1px solid #E5E7EB;border-radius:10px;'
        f'background:#FAFAFA;margin-bottom:4px;">'

        # Title line shimmer
        f'<div style="height:13px;border-radius:6px;width:55%;{shimmer}margin-bottom:10px;"></div>'
        # Body lines
        f'<div style="height:10px;border-radius:4px;width:90%;{shimmer}margin-bottom:6px;"></div>'
        f'<div style="height:10px;border-radius:4px;width:75%;{shimmer}margin-bottom:6px;"></div>'
        f'<div style="height:10px;border-radius:4px;width:82%;{shimmer}"></div>'

        # Status tag
        f'<div style="margin-top:12px;display:inline-flex;align-items:center;gap:6px;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:#2563EB;'
        f'animation:ai-pulse 1s ease-in-out infinite;display:inline-block;"></span>'
        f'<span style="font-size:11px;color:#6B7280;">{label}</span>'
        f'</div>'

        f'</div>'
    )


def quiz_generating_html(elapsed: int) -> str:
    """Animated card shown while quiz questions are being generated."""
    elapsed_str = f"{elapsed}s" if elapsed > 0 else "starting…"
    bars = "".join(
        f'<div style="width:4px;border-radius:2px;background:#8B5CF6;'
        f'animation:ai-wave-bar 0.9s ease-in-out {0.12*i:.2f}s infinite;"></div>'
        for i in range(8)
    )
    dots = bouncing_dots_html()
    return (
        '<div style="padding:18px 20px;background:#F5F3FF;border:1px solid #DDD6FE;'
        'border-radius:12px;display:flex;align-items:center;gap:16px;">'

        '<div style="flex-shrink:0;width:42px;height:42px;border-radius:50%;'
        'background:#7C3AED;display:flex;align-items:center;justify-content:center;">'
        '<div style="font-size:20px;">❓</div>'
        '</div>'

        '<div style="flex:1;">'
        '<div style="font-weight:600;color:#4C1D95;font-size:14px;margin-bottom:4px;">'
        f'Generating quiz questions {dots}</div>'
        f'<div style="font-size:12px;color:#6D28D9;">This takes about 20–40 seconds · {elapsed_str}</div>'
        '</div>'

        f'<div style="display:flex;gap:3px;align-items:flex-end;height:28px;flex-shrink:0;">{bars}</div>'
        '</div>'
    )


def saving_status_html(elapsed: int) -> str:
    """Animated card for the database-save step."""
    elapsed_str = f"{elapsed}s" if elapsed > 0 else "starting…"
    return (
        '<div style="padding:16px 20px;background:#ECFDF5;border:1px solid #A7F3D0;'
        'border-radius:12px;display:flex;align-items:center;gap:14px;">'

        '<div style="flex-shrink:0;font-size:28px;animation:ai-spin 3s linear infinite;">'
        '💾</div>'

        '<div>'
        '<div style="font-weight:600;color:#065F46;font-size:14px;margin-bottom:2px;">'
        'Saving module to library…</div>'
        f'<div style="font-size:12px;color:#10B981;">Almost done · {elapsed_str}</div>'
        '</div>'
        '</div>'
    )
