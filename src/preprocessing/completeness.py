"""
Completeness checker for grievance submissions.

Flags submissions that are too short, greeting-only, or lack real content.
"""
import re
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent.parent.parent

# Common greetings / filler phrases that add no informational value
_GREETINGS = {
    "good morning", "good afternoon", "good evening", "good night",
    "respected sir", "respected madam", "dear sir", "dear madam",
    "hello", "hi", "hey", "greetings", "namaste",
    "to whomsoever it may concern",
    "thank you", "thanks", "regards", "kindly look into it",
    "please help", "please assist",
}

# Regex to strip greeting-like sentences from start
_GREETING_PATTERN = re.compile(
    r"^(good\s+(morning|afternoon|evening|night)|respected\s+(sir|madam)|"
    r"dear\s+(sir|madam)|hello|hi|hey|greetings|namaste)[\.,!]?\s*",
    re.IGNORECASE,
)
_VAGUE_REQUEST_PATTERN = re.compile(
    r"^(?:the\s+)?(?:issue|problem|request)\s+(?:is\s+)?"
    r"(?:not\s+solved|not\s+done|unresolved)"
    r"(?:\s+(?:yet|again|asap|please|kindly))*[.!?]*$",
    re.IGNORECASE,
)


def _load_settings() -> dict:
    p = BASE_DIR / "config" / "settings.yaml"
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_greeting_only(text: str) -> bool:
    """Return True if the text (lowercased) consists solely of greeting phrases."""
    normalized = text.lower().strip()
    # Strip trailing punctuation / thanks
    normalized = re.sub(
        r"[\.,!]?\s*(thank you|thanks|regards|kindly look into it|please help)\.?$",
        "",
        normalized,
    ).strip()
    # Try stripping opening greeting
    stripped = _GREETING_PATTERN.sub("", normalized).strip()
    if not stripped:
        return True
    # Check if only filler words remain
    words = set(stripped.split())
    return words.issubset({"sir", "madam", "please", "kindly", "help", "assist"})


def check_completeness(description: str, message_type: str = "Grievance") -> dict:
    """
    Validate that a grievance description contains enough real content.

    Returns
    -------
    dict with keys:
        complete   : bool
        issues     : list[str]
        word_count : int
    """
    settings = _load_settings()
    min_words: int = settings["completeness"]["min_description_words"]
    min_chars: int = settings["completeness"]["min_description_chars"]

    issues: list[str] = []

    if not description or not description.strip():
        return {
            "complete": False,
            "issues": ["Description is empty."],
            "word_count": 0,
        }

    text = description.strip()
    word_count = len(text.split())
    char_count = len(text)

    if char_count < min_chars:
        issues.append(
            f"Description too short ({char_count} chars; minimum {min_chars})."
        )

    if word_count < min_words:
        issues.append(
            f"Description too brief ({word_count} words; minimum {min_words})."
        )

    if _is_greeting_only(text):
        issues.append(
            "Description appears to be a greeting only, with no actual grievance content."
        )

    if _VAGUE_REQUEST_PATTERN.fullmatch(text):
        issues.append("Please add details identifying what issue remains unresolved.")

    # Check for placeholder-like content
    if re.fullmatch(r"[.\-_*xX]+", text):
        issues.append("Description contains only placeholder characters.")

    return {
        "complete": len(issues) == 0,
        "issues": issues,
        "word_count": word_count,
    }
