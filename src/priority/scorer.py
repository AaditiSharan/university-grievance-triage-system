"""
Priority scoring for UniResolve AI.

Combines sensitivity, completeness, classifier confidence, and urgent-deadline
flag into a single priority label (P1–P4) and numeric score.
"""
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent.parent.parent

_settings_cache: dict | None = None


def _load_settings() -> dict:
    global _settings_cache
    if _settings_cache is None:
        with open(BASE_DIR / "config" / "settings.yaml", "r", encoding="utf-8") as f:
            _settings_cache = yaml.safe_load(f)
    return _settings_cache


def compute_priority(
    sensitivity_result: dict,
    completeness_result: dict,
    classifier_result: dict,
    urgent_deadline: bool = False,
    message_type: str = "Grievance",
) -> dict:
    """
    Compute an overall priority label and numeric score.

    Priority rules (highest-wins):
    - P1: sensitivity_type in SAFETY | MENTAL_HEALTH | MEDICAL
    - P2: urgent_deadline=True, OR (low_confidence AND is_sensitive)
    - P3: normal valid submission
    - P4: enquiries/feedback, Feedback/Suggestions category, OR incomplete description

    Returns
    -------
    dict with keys:
        priority_label : "P1" | "P2" | "P3" | "P4"
        score          : int
        reasons        : list[str]
    """
    settings = _load_settings()
    weights = settings["priority"]["weights"]

    score = 0
    reasons: list[str] = []

    is_sensitive: bool = sensitivity_result.get("is_sensitive", False)
    sensitivity_type: str = sensitivity_result.get("sensitivity_type", "NONE")
    is_complete: bool = completeness_result.get("complete", True)
    low_confidence: bool = classifier_result.get("low_confidence", False)
    predicted_master: str = classifier_result.get("predicted_master", "")
    confidence: float = classifier_result.get("confidence", 0.0)

    # Hard override from sensitivity engine (P1 override)
    if sensitivity_result.get("priority_override") == "P1":
        return {
            "priority_label": "P1",
            "score": 100,
            "reasons": [
                f"Sensitivity rule override: {sensitivity_result.get('matched_rule')} "
                f"({sensitivity_type})"
            ],
        }

    # Score accumulation
    if is_sensitive and sensitivity_type in ("SAFETY", "MENTAL_HEALTH", "MEDICAL"):
        score += weights.get("sensitive", 10)
        reasons.append(f"Sensitive content detected ({sensitivity_type}).")

    if urgent_deadline:
        score += weights.get("urgent_deadline", 5)
        reasons.append("Urgent deadline mentioned.")

    if low_confidence:
        score += weights.get("low_confidence", 2)
        reasons.append(f"Low classifier confidence ({classifier_result.get('confidence', 0):.0%}).")

    if not is_complete:
        score += weights.get("incomplete", 1)
        issues = completeness_result.get("issues", [])
        reasons.append(f"Incomplete submission: {'; '.join(issues)}")
    elif urgent_deadline and not is_sensitive:
        score = max(score, weights.get("urgent_deadline", 5))

    # Map score → label
    if score >= weights.get("sensitive", 10):
        priority_label = "P1"
    elif score >= weights.get("urgent_deadline", 5):
        priority_label = "P2"
    elif is_complete and (
        message_type.strip().lower() in {"query", "enquiry", "feedback", "positive feedback"}
        or (
            predicted_master == "Feedback & Suggestions"
            and confidence >= settings["classifier"]["confidence_threshold"]
        )
    ):
        priority_label = "P4"
        if not reasons:
            reasons.append("Enquiry or feedback submission (low urgency).")
    else:
        priority_label = "P3"
        if not reasons:
            reasons.append("Normal valid submission.")

    return {
        "priority_label": priority_label,
        "score": score,
        "reasons": reasons,
    }
