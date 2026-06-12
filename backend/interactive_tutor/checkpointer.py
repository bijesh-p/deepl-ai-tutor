"""SqliteSaver checkpointer for LangGraph tutor sessions."""
from __future__ import annotations

import os
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

_DB_PATH = os.environ.get("AI_TUTOR_TUTOR_DB_PATH", "data/tutor_sessions.db")


def get_checkpointer() -> SqliteSaver:
    """Return a SqliteSaver for persisting tutor graph state."""
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver.from_conn_string(_DB_PATH)
