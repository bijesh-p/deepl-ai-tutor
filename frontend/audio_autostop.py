"""Stop lingering slide narration audio when the user navigates away.

Streamlit reruns the script synchronously: clicking "Next slide", "Previous
topic", etc. can trigger LLM/audio-generation calls that take a few seconds
before the new page (without the old `st.audio` element) reaches the
browser. Until then the *old* slide's audio keeps playing client-side —
there's no server-side hook to reach back into an already-rendered page.
This renders an invisible iframe whose script listens for button clicks on
the parent page and pauses any playing audio immediately, client-side,
without waiting for the rerun to complete.
"""
from __future__ import annotations

import streamlit as st


def render_audio_autostop() -> None:
    """Render the listener. Call once per page that may have playing audio."""
    st.iframe(
        """
        <html><body>
        <script>
          window.parent.document.addEventListener('click', function(e) {
            if (e.target.closest('button')) {
              window.parent.document.querySelectorAll('audio').forEach(function(a) {
                a.pause();
              });
            }
          }, true);
        </script>
        </body></html>
        """,
        height=1,
    )
