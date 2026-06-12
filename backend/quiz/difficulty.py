from __future__ import annotations

VALID = {"easy", "medium", "hard"}
_ALIASES = {
    "simple": "easy",
    "beginner": "easy",
    "intermediate": "medium",
    "moderate": "medium",
    "difficult": "hard",
    "advanced": "hard",
    "hard": "hard",
}

# Adjacency order used by assembler fallback logic
LEVELS = ["easy", "medium", "hard"]


def validate_difficulty(tag: str) -> str:
    """Normalise a difficulty string to 'easy', 'medium', or 'hard'.

    Accepts common synonyms and is case-insensitive.
    Raises ValueError for unrecognised values.
    """
    normalised = tag.strip().lower()
    if normalised in VALID:
        return normalised
    if normalised in _ALIASES:
        return _ALIASES[normalised]
    raise ValueError(
        f"Unknown difficulty '{tag}'. Expected one of: {', '.join(sorted(VALID))}"
    )


def adjacent_levels(difficulty: str) -> list[str]:
    """Return difficulty levels ordered from closest to furthest from the given level."""
    idx = LEVELS.index(difficulty)
    result = [difficulty]
    for delta in range(1, len(LEVELS)):
        if idx - delta >= 0:
            result.append(LEVELS[idx - delta])
        if idx + delta < len(LEVELS):
            result.append(LEVELS[idx + delta])
    return result
