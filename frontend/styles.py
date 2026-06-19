"""Global CSS injection and reusable HTML component helpers for the AI Tutor UI."""
from __future__ import annotations

import streamlit as st

# ── Design Tokens ────────────────────────────────────────────────────────────
# Base:      #0F172A  (slate-900)  — main background
# Surface:   #1E293B  (slate-800)  — cards, sidebar, elevated panels
# Elevated:  #334155  (slate-700)  — hover states, raised elements
# Border:    #475569  (slate-600)  — subtle borders
# Border-lo: #334155  (slate-700)  — very subtle borders
# Text-1:    #F1F5F9  (slate-100)  — headings, primary text
# Text-2:    #CBD5E1  (slate-300)  — body text, descriptions
# Text-3:    #94A3B8  (slate-400)  — captions, hints, muted
# Text-4:    #64748B  (slate-500)  — disabled, placeholder
# Primary:   #38BDF8  (sky-400)    — primary actions, links
# Primary-h: #0EA5E9  (sky-500)    — primary hover
# Accent:    #818CF8  (indigo-400) — secondary accent, badges
# Success:   #4ADE80  (green-400)  — done, pass
# Warning:   #FBBF24  (amber-400)  — caution
# Error:     #FB7185  (rose-400)   — fail, error

_GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── AI Tutor — Global Dark Theme ────────────────────────────────────── */

html, body, .stApp, .main, .block-container,
input, select, textarea, p, label,
.stMarkdown, .stCaption, .stText,
.stButton > button {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}

.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 960px !important;
}
@media (max-width: 640px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-top: 0.25rem !important;
    }
}

/* ── Typography ────────────────────────────────────────────────────────── */
h1, h2, h3, h4 { margin-top: 0 !important; margin-bottom: 0.5rem !important; }
h1 { font-size: 1.75rem !important; font-weight: 800 !important; letter-spacing: -0.025em !important; color: #F1F5F9 !important; }
h2 { font-size: 1.4rem  !important; font-weight: 700 !important; letter-spacing: -0.015em !important; color: #F1F5F9 !important; }
h3 { font-size: 1.15rem !important; font-weight: 700 !important; letter-spacing: -0.01em  !important; color: #E2E8F0 !important; }
p  { font-size: 1rem    !important; font-weight: 500 !important; line-height: 1.7 !important; color: #CBD5E1 !important; }
li { font-size: 1rem    !important; font-weight: 500 !important; line-height: 1.7 !important; color: #CBD5E1 !important; }
label { font-weight: 600 !important; }

/* ── Buttons ───────────────────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
    padding: 0.5rem 1.1rem !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    min-width: 0 !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0EA5E9 0%, #0284C7 100%) !important;
    border: none !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(14,165,233,0.25) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%) !important;
    box-shadow: 0 4px 16px rgba(14,165,233,0.35) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #38BDF8 !important;
    color: #7DD3FC !important;
    background: rgba(56,189,248,0.08) !important;
}

/* ── Form submit buttons ──────────────────────────────────────────────── */
.stFormSubmitButton > button {
    background: linear-gradient(135deg, #0EA5E9 0%, #0284C7 100%) !important;
    border: none !important;
    color: #FFFFFF !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.2rem !important;
    box-shadow: 0 2px 8px rgba(14,165,233,0.25) !important;
    transition: all 0.15s ease !important;
}
.stFormSubmitButton > button:hover {
    background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%) !important;
    box-shadow: 0 4px 16px rgba(14,165,233,0.35) !important;
    transform: translateY(-1px) !important;
    color: #FFFFFF !important;
}

/* ── Sidebar ───────────────────────────────────────────────────────────── */

[data-testid="stSidebar"] > div:first-child {
    background: #1E293B !important;
    border-right: 1px solid #334155 !important;
    padding: 0.65rem 0.8rem 1rem !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .element-container {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stCaption {
    color: #CBD5E1 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}

[data-testid="stSidebar"] .sb-label {
    font-size: 10px !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.11em !important;
    color: #38BDF8 !important;
    padding: 11px 0 3px !important;
    border-top: 1px solid #334155 !important;
    margin-top: 4px !important;
    line-height: 1 !important;
}

[data-testid="stSidebar"] .stSelectbox { margin-bottom: 4px !important; }
[data-testid="stSidebar"] .stSelectbox label { font-size: 12px !important; color: #38BDF8 !important; font-weight: 600 !important; }
[data-testid="stSidebar"] .stSelectbox > div > div {
    min-height: 32px !important;
    padding: 4px 10px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: 1px solid #475569 !important;
    background: #0F172A !important;
    color: #F1F5F9 !important;
    box-shadow: none !important;
}

/* ── Global selectbox & input styling ─────────────────────────────────── */
.stSelectbox > div > div {
    color: #F1F5F9 !important;
    font-weight: 600 !important;
    background: #1E293B !important;
    border: 1px solid #475569 !important;
}
.stSelectbox div,
.stSelectbox span,
.stSelectbox [data-baseweb="select"] span,
.stSelectbox [data-baseweb="select"] div,
.stSelectbox [data-baseweb="select"] [data-testid="stMarkdownContainer"],
[data-baseweb="select"] > div {
    color: #F1F5F9 !important;
    font-weight: 600 !important;
    opacity: 1 !important;
}
[data-testid="stSidebar"] .stSelectbox div,
[data-testid="stSidebar"] .stSelectbox span,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    color: #F1F5F9 !important;
    font-weight: 600 !important;
    opacity: 1 !important;
}
/* Dropdown menu items */
[data-baseweb="popover"] {
    background: #1E293B !important;
    border: 1px solid #475569 !important;
}
[data-baseweb="popover"] li,
[data-baseweb="popover"] [role="option"] {
    color: #E2E8F0 !important;
    font-weight: 500 !important;
    background: #1E293B !important;
}
[data-baseweb="popover"] li:hover,
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [aria-selected="true"] {
    background: #334155 !important;
    color: #F1F5F9 !important;
}
/* Text inputs */
.stTextInput input {
    color: #F1F5F9 !important;
    font-weight: 500 !important;
    background: #1E293B !important;
    border: 1px solid #475569 !important;
}
.stTextInput input::placeholder {
    color: #64748B !important;
}
.stTextInput input:focus {
    border-color: #38BDF8 !important;
    box-shadow: 0 0 0 3px rgba(56,189,248,0.15) !important;
}

[data-testid="stSidebar"] .stToggle { padding: 1px 0 !important; margin-bottom: 2px !important; }
[data-testid="stSidebar"] .stToggle label,
[data-testid="stSidebar"] .stToggle p {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #CBD5E1 !important;
}

[data-testid="stSidebar"] .element-container .stButton > button {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid #475569 !important;
    color: #CBD5E1 !important;
    width: 100% !important;
    text-align: left !important;
    padding: 5px 11px !important;
    min-height: 32px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    border-radius: 8px !important;
    margin-bottom: 3px !important;
    box-shadow: none !important;
    letter-spacing: 0 !important;
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
[data-testid="stSidebar"] .element-container .stButton > button:hover {
    background: rgba(56,189,248,0.08) !important;
    border-color: #38BDF8 !important;
    color: #F1F5F9 !important;
    box-shadow: 0 1px 4px rgba(56,189,248,0.1) !important;
    transform: none !important;
}

[data-testid="stSidebar"] .element-container:has(.sb-signout-marker) + .element-container .stButton > button {
    background: rgba(251,113,133,0.08) !important;
    border: 1px solid #9F1239 !important;
    color: #FB7185 !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-align: center !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .element-container:has(.sb-signout-marker) + .element-container .stButton > button:hover {
    background: rgba(251,113,133,0.15) !important;
    border-color: #E11D48 !important;
    color: #FDA4AF !important;
}

[data-testid="stSidebar"] hr { display: none !important; }
[data-testid="stSidebar"] .element-container { margin-bottom: 0 !important; }
[data-testid="stSidebar"] .stMarkdown { margin-bottom: 0 !important; }

/* ── Progress bar ──────────────────────────────────────────────────────── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #0EA5E9 0%, #818CF8 100%) !important;
    border-radius: 999px !important;
}

/* ── Metrics ────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #1E293B !important;
    border: 1px solid #334155 !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
}
[data-testid="stMetricValue"] { color: #38BDF8 !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #94A3B8 !important; font-weight: 700 !important; font-size: 0.9rem !important; }

/* ── Alert boxes ────────────────────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: 10px !important; }

/* ── Expanders ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #334155 !important;
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
.stTabs [aria-selected="true"] { color: #38BDF8 !important; }

/* ── Forms ──────────────────────────────────────────────────────────────── */
[data-testid="stForm"] {
    border-radius: 12px !important;
    border: 1px solid #334155 !important;
    background: #1E293B !important;
}

/* ── File uploader ──────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border-radius: 10px !important;
}

/* ── Toggle ─────────────────────────────────────────────────────────────── */
[data-testid="stToggle"] label { font-weight: 500 !important; }

/* ── Quiz option cards ─────────────────────────────────────────────────── */

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

[data-testid="stRadio"] [role="radiogroup"] > label {
    counter-increment: quiz-opt !important;
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 14px 18px 14px 14px !important;
    border: 2px solid #334155 !important;
    border-radius: 12px !important;
    background: #1E293B !important;
    cursor: pointer !important;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease !important;
    box-sizing: border-box !important;
    margin-bottom: 0 !important;
    position: relative !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:hover {
    border-color: #0EA5E9 !important;
    background: #263548 !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
    border-color: #38BDF8 !important;
    background: rgba(56,189,248,0.08) !important;
    box-shadow: 0 0 0 3px rgba(56,189,248,0.12) !important;
}

[data-testid="stRadio"] [role="radiogroup"] > label::before {
    content: counter(quiz-opt, upper-alpha) !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: 28px !important;
    height: 28px !important;
    border-radius: 50% !important;
    background: #334155 !important;
    color: #94A3B8 !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    margin-right: 14px !important;
    flex-shrink: 0 !important;
    font-family: 'Inter', sans-serif !important;
    transition: background 0.15s ease, color 0.15s ease !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:hover::before {
    background: #475569 !important;
    color: #E2E8F0 !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked)::before {
    background: #0EA5E9 !important;
    color: #FFFFFF !important;
}

[data-testid="stRadio"] [role="radiogroup"] > label p,
[data-testid="stRadio"] [role="radiogroup"] > label div {
    font-size: 15px !important;
    font-weight: 500 !important;
    color: #CBD5E1 !important;
    line-height: 1.5 !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p,
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) div {
    color: #7DD3FC !important;
    font-weight: 600 !important;
}

[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child {
    display: none !important;
}

[data-testid="stCheckbox"] label {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 14px 18px !important;
    border: 2px solid #334155 !important;
    border-radius: 12px !important;
    background: #1E293B !important;
    cursor: pointer !important;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease !important;
    box-sizing: border-box !important;
    margin-bottom: 8px !important;
    gap: 12px !important;
}
[data-testid="stCheckbox"] label:hover {
    border-color: #0EA5E9 !important;
    background: #263548 !important;
}
[data-testid="stCheckbox"] label:has(input:checked) {
    border-color: #38BDF8 !important;
    background: rgba(56,189,248,0.08) !important;
    box-shadow: 0 0 0 3px rgba(56,189,248,0.12) !important;
}
[data-testid="stCheckbox"] label p,
[data-testid="stCheckbox"] label span {
    font-size: 15px !important;
    font-weight: 500 !important;
    color: #CBD5E1 !important;
    line-height: 1.5 !important;
}
[data-testid="stCheckbox"] label:has(input:checked) p,
[data-testid="stCheckbox"] label:has(input:checked) span {
    color: #7DD3FC !important;
    font-weight: 600 !important;
}

/* ── Hide Streamlit dev-mode chrome ────────────────────────────────────── */
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
  0%, 100% { box-shadow: 0 0 0 0   rgba(56,189,248,0.45); }
  50%       { box-shadow: 0 0 0 8px rgba(56,189,248,0);    }
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


def inject_global_css() -> None:
    """Inject global CSS. Call once at the top of app.py after set_page_config."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


# ── Reusable HTML components ────────────────────────────────────────────────

_STEP_COLORS = {
    "done":    ("background:#4ADE80;color:#052E16;", "color:#4ADE80;font-weight:600;", "#4ADE80"),
    "active":  ("background:#0EA5E9;color:white;box-shadow:0 0 0 4px rgba(14,165,233,0.25);", "color:#7DD3FC;font-weight:700;", "#0EA5E9"),
    "pending": ("background:#334155;color:#64748B;", "color:#64748B;", "#334155"),
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
            bar_bg = "#4ADE80" if is_done_bar else "#334155"
            bar_anim = ""
            if i + 1 == current_idx:
                bar_anim = (
                    "background:linear-gradient(90deg,#4ADE80 0%,#0EA5E9 50%,#334155 100%);"
                    "background-size:200% 100%;animation:ai-shimmer 2s linear infinite;"
                )
            bar_style = bar_anim if bar_anim else f"background:{bar_bg};"
            parts.append(
                f'<div style="flex:1;height:2px;{bar_style}margin:0 4px;margin-top:-19px;border-radius:2px;"></div>'
            )

    inner = "".join(parts)
    return (
        f'<div style="display:flex;align-items:flex-start;padding:0.9rem 1.25rem 1rem;'
        f'background:#1E293B;border-radius:12px;border:1px solid #334155;margin-bottom:1rem;">'
        f'{inner}</div>'
    )


def module_card_html(title: str, source: str, date_label: str, is_published: bool = False) -> str:
    """Info section of a module card (title + meta)."""
    pub = ('<span style="display:inline-block;background:rgba(74,222,128,0.12);color:#4ADE80;font-size:10px;'
           'padding:2px 8px;border-radius:999px;font-weight:600;margin-left:8px;">Published</span>'
           if is_published else "")
    return f"""<div style="padding:14px 18px;background:#1E293B;border:1px solid #334155;border-left:4px solid #0EA5E9;border-radius:10px;margin-bottom:6px;">
  <div style="font-weight:600;font-size:15px;color:#F1F5F9;margin-bottom:5px;">{title}{pub}</div>
  <div style="font-size:12px;color:#94A3B8;">{source}</div>
  <div style="font-size:11px;color:#64748B;margin-top:3px;">{date_label}</div>
</div>"""


def score_banner_html(score: int, total: int, pct: float) -> str:
    """Large score display for the quiz results page."""
    if pct >= 70:
        fg, bg, border, grade = "#4ADE80", "rgba(74,222,128,0.06)", "#166534", "Excellent!" if pct >= 90 else "Well done!"
        ring = "#4ADE80"
    elif pct >= 50:
        fg, bg, border, grade = "#FBBF24", "rgba(251,191,36,0.06)", "#78350F", "Keep practicing!"
        ring = "#FBBF24"
    else:
        fg, bg, border, grade = "#FB7185", "rgba(251,113,133,0.06)", "#9F1239", "Needs more study"
        ring = "#FB7185"

    return f"""<div style="text-align:center;padding:2.5rem 2rem;background:{bg};border:2px solid {border};border-radius:20px;margin:0.75rem 0 1.5rem;">
  <div style="display:inline-flex;align-items:center;justify-content:center;width:110px;height:110px;border-radius:50%;border:6px solid {ring};background:#0F172A;margin-bottom:1rem;">
    <div style="font-size:2.25rem;font-weight:800;color:{fg};line-height:1;">{pct:.0f}<span style="font-size:1.1rem;">%</span></div>
  </div>
  <div style="font-size:1.3rem;font-weight:700;color:{fg};margin-bottom:4px;">{grade}</div>
  <div style="font-size:0.95rem;color:#94A3B8;">{score} of {total} questions correct</div>
</div>"""


def question_card_html(number: int, text: str, q_type: str) -> str:
    """Decorative card header for a quiz question."""
    badge_color = "rgba(56,189,248,0.12)" if q_type == "single_choice" else "rgba(129,140,248,0.12)"
    badge_text_color = "#7DD3FC" if q_type == "single_choice" else "#A5B4FC"
    badge_label = "Single choice" if q_type == "single_choice" else "Multi choice"
    return f"""<div style="padding:14px 18px 10px;background:#1E293B;border:1px solid #334155;border-radius:10px;margin-bottom:-8px;border-bottom:none;border-bottom-left-radius:0;border-bottom-right-radius:0;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
    <div style="min-width:26px;height:26px;border-radius:50%;background:#0EA5E9;color:white;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;">{number}</div>
    <div style="font-weight:600;font-size:14px;color:#F1F5F9;flex:1;">{text}</div>
    <span style="background:{badge_color};color:{badge_text_color};font-size:10px;padding:2px 8px;border-radius:999px;font-weight:600;white-space:nowrap;">{badge_label}</span>
  </div>
</div>"""


def page_header_html(title: str, subtitle: str = "", icon: str = "") -> str:
    """Branded page header banner."""
    icon_html = f'<div style="font-size:2rem;margin-bottom:0.4rem;">{icon}</div>' if icon else ""
    sub_html = f'<div style="font-size:0.95rem;color:#94A3B8;margin-top:4px;">{subtitle}</div>' if subtitle else ""
    return (
        f'<div style="padding:1.5rem 2rem;background:#1E293B;'
        f'border-radius:14px;border:1px solid #334155;margin-bottom:1.5rem;">'
        f'{icon_html}'
        f'<h1 style="margin:0;font-size:1.6rem;font-weight:800;color:#F1F5F9;">{title}</h1>'
        f'{sub_html}</div>'
    )


# ── Animated pipeline status components ────────────────────────────────────

def bouncing_dots_html() -> str:
    """Three bouncing dots — used inline to show active LLM work."""
    d = "width:8px;height:8px;border-radius:50%;background:#38BDF8;display:inline-block;"
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
        '<div style="padding:18px 20px;background:#1E293B;border:1px solid #334155;'
        'border-radius:12px;display:flex;align-items:center;gap:16px;">'

        '<div style="flex-shrink:0;width:42px;height:42px;border-radius:50%;'
        'background:#0EA5E9;display:flex;align-items:center;justify-content:center;">'
        '<div style="font-size:20px;animation:ai-spin 2s linear infinite;">🔍</div>'
        '</div>'

        '<div style="flex:1;">'
        f'<div style="font-weight:600;color:#7DD3FC;font-size:14px;margin-bottom:3px;">{detail}</div>'
        f'<div style="font-size:12px;color:#38BDF8;">Elapsed: {elapsed_str}</div>'
        '</div>'

        '<div style="display:flex;gap:3px;align-items:flex-end;height:28px;flex-shrink:0;">'
        + "".join(
            f'<div style="width:4px;border-radius:2px;background:#0EA5E9;'
            f'animation:ai-wave-bar 1s ease-in-out {0.1*i:.1f}s infinite;"></div>'
            for i in range(6)
        )
        + '</div></div>'
    )


def slide_chips_html(enriched_topics: list, current_topic: str, total_topics: int) -> str:
    """Row of slide chips: green for done, pulsing sky for current."""
    if not enriched_topics and not current_topic:
        return ""

    chips: list[str] = []

    for et in enriched_topics:
        title = getattr(getattr(et, "topic", None), "title", str(et))
        short = (title[:22] + "…") if len(title) > 22 else title
        chips.append(
            f'<div style="display:inline-flex;align-items:center;gap:5px;'
            f'padding:4px 10px;background:rgba(74,222,128,0.1);border:1px solid #166534;'
            f'border-radius:999px;font-size:11px;color:#4ADE80;font-weight:500;'
            f'animation:ai-slide-in 0.35s ease-out;">'
            f'<span style="font-size:10px;">✓</span>{short}</div>'
        )

    if current_topic:
        short = (current_topic[:22] + "…") if len(current_topic) > 22 else current_topic
        chips.append(
            f'<div style="display:inline-flex;align-items:center;gap:6px;'
            f'padding:4px 12px;background:rgba(56,189,248,0.1);border:1px solid #075985;'
            f'border-radius:999px;font-size:11px;color:#7DD3FC;font-weight:600;'
            f'animation:ai-pulse 1.4s ease-in-out infinite;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:#38BDF8;'
            f'animation:ai-pulse 0.9s ease-in-out infinite;display:inline-block;"></span>'
            f'{short}…</div>'
        )

    inner = "\n".join(chips)
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 14px;">'
        f'{inner}</div>'
    )


def skeleton_slide_html(label: str = "Generating slide content…") -> str:
    """Shimmering skeleton card indicating an LLM call is in flight."""
    shimmer = (
        "background:linear-gradient(90deg,#1E293B 25%,#334155 50%,#1E293B 75%);"
        "background-size:600px 100%;animation:ai-shimmer 1.6s linear infinite;"
    )
    return (
        f'<div style="padding:16px 18px;border:1px solid #334155;border-radius:10px;'
        f'background:#1E293B;margin-bottom:4px;">'

        f'<div style="height:13px;border-radius:6px;width:55%;{shimmer}margin-bottom:10px;"></div>'
        f'<div style="height:10px;border-radius:4px;width:90%;{shimmer}margin-bottom:6px;"></div>'
        f'<div style="height:10px;border-radius:4px;width:75%;{shimmer}margin-bottom:6px;"></div>'
        f'<div style="height:10px;border-radius:4px;width:82%;{shimmer}"></div>'

        f'<div style="margin-top:12px;display:inline-flex;align-items:center;gap:6px;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:#0EA5E9;'
        f'animation:ai-pulse 1s ease-in-out infinite;display:inline-block;"></span>'
        f'<span style="font-size:11px;color:#94A3B8;">{label}</span>'
        f'</div>'

        f'</div>'
    )


def quiz_generating_html(elapsed: int) -> str:
    """Animated card shown while quiz questions are being generated."""
    elapsed_str = f"{elapsed}s" if elapsed > 0 else "starting…"
    bars = "".join(
        f'<div style="width:4px;border-radius:2px;background:#818CF8;'
        f'animation:ai-wave-bar 0.9s ease-in-out {0.12*i:.2f}s infinite;"></div>'
        for i in range(8)
    )
    dots = bouncing_dots_html()
    return (
        '<div style="padding:18px 20px;background:#1E293B;border:1px solid #334155;'
        'border-radius:12px;display:flex;align-items:center;gap:16px;">'

        '<div style="flex-shrink:0;width:42px;height:42px;border-radius:50%;'
        'background:#7C3AED;display:flex;align-items:center;justify-content:center;">'
        '<div style="font-size:20px;">❓</div>'
        '</div>'

        '<div style="flex:1;">'
        '<div style="font-weight:600;color:#C4B5FD;font-size:14px;margin-bottom:4px;">'
        f'Generating quiz questions {dots}</div>'
        f'<div style="font-size:12px;color:#A78BFA;">This takes about 20–40 seconds · {elapsed_str}</div>'
        '</div>'

        f'<div style="display:flex;gap:3px;align-items:flex-end;height:28px;flex-shrink:0;">{bars}</div>'
        '</div>'
    )


def saving_status_html(elapsed: int) -> str:
    """Animated card for the database-save step."""
    elapsed_str = f"{elapsed}s" if elapsed > 0 else "starting…"
    return (
        '<div style="padding:16px 20px;background:rgba(74,222,128,0.06);border:1px solid #166534;'
        'border-radius:12px;display:flex;align-items:center;gap:14px;">'

        '<div style="flex-shrink:0;font-size:28px;animation:ai-spin 3s linear infinite;">'
        '💾</div>'

        '<div>'
        '<div style="font-weight:600;color:#4ADE80;font-size:14px;margin-bottom:2px;">'
        'Saving module to library…</div>'
        f'<div style="font-size:12px;color:#86EFAC;">Almost done · {elapsed_str}</div>'
        '</div>'
        '</div>'
    )
