"""
Text normalisation and Hinglish preprocessing for UniResolve AI.
"""
import re

# Common Hinglish → English token mappings
HINGLISH_MAP: dict[str, str] = {
    "kab": "when",
    "kaise": "how",
    "kya": "what",
    "nahi": "not",
    "nhi": "not",
    "hai": "is",
    "ho": "is",
    "hain": "are",
    "mein": "in",
    "main": "i",
    "se": "from",
    "ka": "of",
    "ki": "of",
    "ke": "of",
    "ko": "to",
    "please": "please",
    "karein": "please do",
    "karo": "do",
    "milega": "will get",
    "milegi": "will get",
    "dikkat": "problem",
    "aati": "comes",
    "aayi": "came",
    "chahiye": "needed",
    "chahie": "needed",
    "abhi": "now",
    "bahut": "very",
    "sab": "all",
    "aur": "and",
    "ya": "or",
    "lekin": "but",
    "kyunki": "because",
    "jab": "when",
    "tab": "then",
    "mere": "my",
    "mera": "my",
    "meri": "my",
    "humara": "our",
    "humari": "our",
    "unka": "their",
    "iska": "its",
    "yaha": "here",
    "waha": "there",
    "theek": "okay",
    "sahi": "correct",
    "galat": "wrong",
    "problem": "problem",
    "parishaan": "troubled",
    "paresaan": "troubled",
    "mushkil": "difficulty",
    "kaam": "work",
    "band": "closed",
    "khula": "open",
    "kal": "tomorrow",
    "aaj": "today",
    "roz": "daily",
    "dhamki": "threat",
    "maarne": "attack",
    "maarna": "attack",
    "maar": "hit",
    "chot": "injury",
    "bukhar": "fever",
    "tez": "high",
    "pareshan": "harassment",
    "khud": "self",
    "nuksaan": "harm",
}


def _apply_hinglish_map(text: str) -> str:
    """Replace Hinglish tokens using HINGLISH_MAP (whole-word match)."""
    pattern = r"\b(" + "|".join(
        map(re.escape, sorted(HINGLISH_MAP, key=len, reverse=True))
    ) + r")\b"
    return re.sub(pattern, lambda match: HINGLISH_MAP[match.group(0)], text)


def translate_hinglish(text: str) -> str:
    """Public wrapper: replace known Hinglish tokens with their English equivalents."""
    return _apply_hinglish_map(text)


def clean_text(text: str) -> str:
    """
    Normalise raw grievance text:
    1. Lowercase
    2. Collapse Unicode whitespace
    3. Remove non-printable / control chars
    4. Normalise punctuation (keep alphanumeric, spaces, basic punctuation)
    5. Apply Hinglish token substitution
    """
    if not isinstance(text, str):
        text = str(text)

    # Lowercase
    text = text.lower()

    # Remove carriage returns, tabs → space
    text = re.sub(r"[\r\n\t]+", " ", text)

    # Keep alphanumeric characters, whitespace and basic punctuation.
    text = re.sub(r"[^\w\s.,!?;:\-'\"()%@#/]", " ", text)

    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text).strip()

    # Apply Hinglish substitution without losing punctuation boundaries.
    text = _apply_hinglish_map(text)

    # Final collapse
    text = re.sub(r"\s{2,}", " ", text).strip()

    return text


def normalize_description(description: str) -> str:
    """
    Full normalisation pipeline for a grievance description.
    Calls clean_text and collapses any remaining whitespace.
    """
    cleaned = clean_text(description)
    # Collapse any residual whitespace
    cleaned = " ".join(cleaned.split())
    return cleaned