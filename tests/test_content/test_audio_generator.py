"""Tests for audio_generator's narration assembly (pure string logic, no TTS calls).

Covers two fixes: diagrams are no longer narrated (only shown), and emoji
characters are stripped before being handed to the TTS engine.
"""
from backend.content.audio_generator import _build_script, _describe_bullets, _strip_emoji


def test_build_script_does_not_narrate_diagram_structure():
    script = _build_script(
        text="Plants convert light into energy.",
        bullets=[],
        topic_title="Photosynthesis",
    )

    assert "diagram" not in script.lower()
    assert "flow" not in script.lower()
    assert "Now let's explore: Photosynthesis." in script
    assert "Plants convert light into energy." in script


def test_build_script_bullets_anchor_unchanged():
    script = _build_script(
        text="Here is more detail.",
        bullets=["Point one", "Point two"],
        topic_title="Cells",
    )

    assert script == (
        "Now let's explore: Cells.\n\n"
        "Here are the key ideas for this topic. Point 1: Point one Point 2: Point two\n\n"
        "Here is more detail."
    )


def test_build_script_strips_emoji_from_final_output():
    script = _build_script(
        text="The \U0001F7E2 green node represents growth.",
        bullets=[],
        topic_title="Growth",
    )

    assert "\U0001F7E2" not in script
    assert "The  green node represents growth." in script


def test_strip_emoji_removes_emoji_leaves_prose_intact():
    result = _strip_emoji("Let's look at the \U0001F7E2 green node.")
    assert "\U0001F7E2" not in result
    assert "Let's look at the  green node." == result


def test_strip_emoji_is_noop_on_plain_text():
    text = "This is plain English text with no special characters."
    assert _strip_emoji(text) == text


def test_describe_bullets_unaffected_by_diagram_removal():
    assert _describe_bullets(["A", "B"]) == "Here are the key ideas for this topic. Point 1: A Point 2: B"
    assert _describe_bullets([]) == ""
