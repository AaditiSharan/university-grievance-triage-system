"""
Sensitivity engine for UniResolve AI.

Loads sensitivity_rules.yaml and applies each rule to the cleaned text.
Returns a structured result indicating whether the submission is sensitive,
which rule matched, and routing / review recommendations.
"""
import re
from pathlib import Path
from typing import Optional

import yaml

BASE_DIR = Path(__file__).parent.parent.parent

_RULES_CACHE: Optional[list] = None


def _load_rules() -> list:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        rules_path = BASE_DIR / "config" / "sensitivity_rules.yaml"
        with open(rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _RULES_CACHE = data.get("rules", [])
    return _RULES_CACHE


def _phrase_in_text(phrase: str, text: str) -> bool:
    """Return True if *phrase* appears as a whole phrase in *text*."""
    # Escape regex special chars in the phrase
    pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
    return bool(pattern.search(text))


def _phrase_is_asserted(phrase: str, text: str) -> bool:
    """Ignore negated and anti-awareness mentions of a sensitive phrase."""
    pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 60):match.start()]
        suffix = text[match.end():match.end() + 30]
        if re.search(
            r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\banti\s*-\s*|\banti\s+)"
            r"(?:[\w'-]+\s+){0,3}\s*$",
            prefix,
        ):
            continue
        if re.match(r"\s*(?:not|never|isn't|aren't|wasn't|weren't)\b", suffix):
            continue
        return True
    return False


def check_sensitivity(text: str) -> dict:
    """
    Apply all sensitivity rules to *text*.

    Returns
    -------
    dict with keys:
        is_sensitive      : bool
        sensitivity_type  : str   (NONE | SAFETY | MENTAL_HEALTH | MEDICAL | CONFIDENTIAL)
        matched_rule      : str   (rule name or empty string)
        matched_keywords  : list[str]
        priority_override : str | None  (e.g. "P1")
        route_override    : str | None
        needs_human_review: bool
        evidence          : list[str]
    """
    rules = _load_rules()
    text_lower = str(text or "").lower()

    result = {
        "is_sensitive": False,
        "sensitivity_type": "NONE",
        "matched_rule": "",
        "matched_keywords": [],
        "priority_override": None,
        "route_override": None,
        "needs_human_review": False,
        "evidence": [],
        "deadline_detected": False,
    }

    # Process rules in order; first hard-sensitivity match wins, while deadline
    # and confidentiality evidence is collected independently.
    primary_match: Optional[dict] = None
    secondary_flags: list[dict] = []

    for rule in rules:
        keywords: list = rule.get("keywords", [])
        matched_kws = [
            kw for kw in keywords
            if _phrase_is_asserted(str(kw), text_lower)
        ]

        if not matched_kws:
            continue

        rule_type: str = rule.get("type", "UNKNOWN")

        if rule_type in ("SAFETY", "MENTAL_HEALTH", "MEDICAL"):
            candidate = {
                "rule": rule,
                "matched_keywords": matched_kws,
                "type": rule_type,
            }
            if primary_match is None:
                primary_match = candidate
            else:
                secondary_flags.append(candidate)
        else:
            # DEADLINE / CONFIDENTIAL – add to secondary flags
            secondary_flags.append({
                "rule": rule,
                "matched_keywords": matched_kws,
                "type": rule_type,
            })
            if rule_type == "DEADLINE":
                result["deadline_detected"] = True

    # Build result -----------------------------------------------------------
    if primary_match:
        rule = primary_match["rule"]
        result["is_sensitive"] = True
        result["sensitivity_type"] = primary_match["type"]
        result["matched_rule"] = rule.get("name", "")
        result["matched_keywords"] = primary_match["matched_keywords"]
        result["priority_override"] = rule.get("priority")
        result["route_override"] = rule.get("route")
        result["needs_human_review"] = rule.get("human_review", True)
        result["evidence"] = [
            f"Rule {rule.get('id')} ({rule.get('name')}): "
            f"matched keywords {primary_match['matched_keywords']}"
        ]

        # Append secondary evidence
        for sec in secondary_flags:
            result["evidence"].append(
                f"Also matched Rule {sec['rule'].get('id')} "
                f"({sec['rule'].get('name')}): {sec['matched_keywords']}"
            )

    elif secondary_flags:
        confidential = next(
            (flag for flag in secondary_flags if flag["type"] == "CONFIDENTIAL"),
            None,
        )
        for flag in secondary_flags:
            result["evidence"].append(
                f"Rule {flag['rule'].get('id')} ({flag['rule'].get('name')}): "
                f"matched keywords {flag['matched_keywords']}"
            )
        if confidential:
            rule = confidential["rule"]
            result["is_sensitive"] = True
            result["sensitivity_type"] = confidential["type"]
            result["matched_rule"] = rule.get("name", "")
            result["matched_keywords"] = confidential["matched_keywords"]
            result["route_override"] = rule.get("route")
            result["needs_human_review"] = rule.get("human_review", True)

    deadline_pattern = re.compile(
        r"\b(?:deadline|due(?:\s+date)?|due\s+by|by\s+(?:today|tomorrow|this\s+week|next\s+week)|tomorrow|today|before\s+(?:end\s+of\s+day|5\s*pm|6\s*pm|11\s*:\s*59\s*(?:pm|am)))\b",
        re.IGNORECASE,
    )
    if not result["is_sensitive"] and deadline_pattern.search(text_lower):
        result["deadline_detected"] = True
        result["evidence"].append("Deadline context detected; urgency considered without sensitivity escalation.")

    return result
