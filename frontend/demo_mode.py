from __future__ import annotations

import uuid
from pathlib import Path

import streamlit as st

from content.models import LearningModule
from quiz.models import QuestionBank, QuizResult, AnswerResult
from analytics.models import ModuleStats

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"

_DEMO_USER_ID = "demo-user-0000"
_DEMO_USERNAME = "Demo User"


def render_demo_toggle() -> None:
    """Render the Demo Mode toggle in the sidebar. Persists across all pages."""
    with st.sidebar:
        st.markdown("---")
        demo = st.toggle(
            "🧪 Demo Mode",
            value=st.session_state.get("demo_mode", False),
            help=(
                "Enable Demo Mode to explore the full app without a PDF or API key. "
                "All content is loaded from pre-built sample data."
            ),
        )
        if demo != st.session_state.get("demo_mode", False):
            # Reset to upload page when toggling
            st.session_state["demo_mode"] = demo
            for key in ["module", "bank", "doc", "current_quiz", "quiz_answers",
                        "quiz_submitted", "quiz_result", "quiz_stats"]:
                st.session_state.pop(key, None)
            st.session_state["page"] = "upload"
            st.rerun()

        if st.session_state.get("demo_mode"):
            st.info("Demo Mode is **on** — using sample data.")


def is_demo() -> bool:
    return st.session_state.get("demo_mode", False)


def load_demo_session() -> None:
    """Load fixture data into session state to simulate a completed pipeline run."""
    module = LearningModule.from_json((FIXTURES / "sample_module.json").read_text())
    bank = QuestionBank.from_json((FIXTURES / "sample_bank.json").read_text())

    db_path = ":memory:"  # no real DB writes in demo mode

    st.session_state["module"] = module
    st.session_state["bank"] = bank
    st.session_state["user_id"] = _DEMO_USER_ID
    st.session_state["username"] = _DEMO_USERNAME
    st.session_state["db_path"] = db_path
    st.session_state["page"] = "learn"


def load_demo_result() -> tuple[QuizResult, ModuleStats]:
    """Return fixture QuizResult and ModuleStats for the results page demo."""
    result = QuizResult.from_json((FIXTURES / "sample_result.json").read_text())
    stats = ModuleStats.from_json((FIXTURES / "sample_stats.json").read_text())
    return result, stats
