
"""
Sensitivity engine for UniResolve AI.

Loads sensitivity_rules.yaml and applies each rule to the cleaned text.
Returns a structured result indicating whether the submission is sensitive,
which rules matched, and routing / review recommendations.

Behaviour documented at the top of sensitivity_rules.yaml and implemented here:

* ``exclusions``  - a keyword match that overlaps an exclusion phrase is
  discarded (other occurrences elsewhere in the text still count).
* ``route_precedence`` - when several rules fire, the route and alert level
  come from the rule that appears earliest in that list; every other fired
  rule is still recorded as evidence.
* Safety-critical flags are combined across *all* fired rules, never taken
  from the primary rule alone: any rule that forbids auto-replies blocks them,
  any rule that requires human review forces it, and the most urgent priority
  wins.
* Hinglish: rule keywords and exclusions are translated with the same Hinglish
  map the cleaner applies to submissions, so a keyword written in Hinglish in
  the YAML ("seniors ne dhamki") still matches cleaned text ("seniors ne threat").
* The rules file is validated when it is loaded (and at API startup).

Negation handling is deliberately conservative. Only a small set of clear
patterns ("no ragging", "there isn't any ragging", "anti-ragging", "ragging is
not happening") suppresses a match. Anything the engine cannot confidently read
as a negation counts as an assertion, so the grievance is flagged for a human
rather than silently ignored. Simple patterns cannot understand sarcasm or
complex sentences; when unsure, a false flag is the intended failure mode.
"""
import re
from pathlib import Path
from typing import Iterable, Optional

import yaml

from src.preprocessing.cleaner import translate_hinglish

BASE_DIR = Path(__file__).parent.parent.parent

# Rule types that are a hard escalation (priority override, forced review).
# "WELFARE" is the type used by sensitivity_rules.yaml (R-004, R-006) and by
# the dataset. "MENTAL_HEALTH" is kept as a legacy alias so older rule files
# keep working.
HARD_SENSITIVITY_TYPES = frozenset({"SAFETY", "WELFARE", "MEDICAL", "MENTAL_HEALTH"})
# Types that make a submission sensitive and must declare the full policy block.
ESCALATING_TYPES = HARD_SENSITIVITY_TYPES | {"CONFIDENTIAL"}
ALLOWED_RULE_TYPES = ESCALATING_TYPES | {"DEADLINE"}
VALID_PRIORITIES = ("P1", "P2", "P3", "P4")

_CONFIG_CACHE: Optional[dict] = None


# ---------------------------------------------------------------------------
# Configuration loading and validation
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Lower-case, straighten apostrophes, and translate Hinglish tokens."""
    return translate_hinglish(str(text or "").lower().replace("\u2019", "'"))


def _read_raw_config() -> dict:
    rules_path = BASE_DIR / "config" / "sensitivity_rules.yaml"
    # utf-8-sig tolerates the byte-order mark some editors add.
    with open(rules_path, "r", encoding="utf-8-sig") as f:
        return yaml.safe_load(f) or {}


def _routing_destinations() -> set:
    """Every office a rule is allowed to route to (from routing_table.yaml)."""
    path = BASE_DIR / "config" / "routing_table.yaml"
    with open(path, "r", encoding="utf-8-sig") as f:
        data = yaml.safe_load(f) or {}
    destinations = set((data.get("routes") or {}).values())
    for key in ("default", "unclear"):
        if data.get(key):
            destinations.add(data[key])
    return destinations


def validate_config(data: dict, routing_destinations: Optional[set] = None) -> list:
    """
    Check a parsed rules file and return a list of problems (empty = valid).

    Checks: non-empty rule list, unique ids, required fields, allowed rule
    types, valid priority labels, boolean policy flags, routes that exist in
    the routing table (when *routing_destinations* is given), and that
    route_precedence names known, non-duplicate rule ids.
    """
    problems: list = []
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules:
        return ["'rules' must be a non-empty list"]

    seen_ids: set = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            problems.append(f"rules[{index}] must be a mapping")
            continue

        rule_id = rule.get("id")
        label = f"rule {rule_id!r}" if rule_id else f"rules[{index}]"
        if not isinstance(rule_id, str) or not rule_id.strip():
            problems.append(f"rules[{index}] is missing 'id'")
        elif rule_id in seen_ids:
            problems.append(f"duplicate rule id {rule_id!r}")
        else:
            seen_ids.add(rule_id)

        if not str(rule.get("name") or "").strip():
            problems.append(f"{label}: missing 'name'")

        rule_type = rule.get("type")
        if rule_type not in ALLOWED_RULE_TYPES:
            problems.append(
                f"{label}: type {rule_type!r} must be one of {sorted(ALLOWED_RULE_TYPES)}"
            )

        keywords = rule.get("keywords")
        if (
            not isinstance(keywords, list)
            or not keywords
            or not all(isinstance(k, str) and k.strip() for k in keywords)
        ):
            problems.append(f"{label}: 'keywords' must be a non-empty list of non-empty strings")

        exclusions = rule.get("exclusions", [])
        if exclusions is None:
            exclusions = []
        if not isinstance(exclusions, list) or not all(
            isinstance(x, str) and x.strip() for x in exclusions
        ):
            problems.append(f"{label}: 'exclusions' must be a list of non-empty strings")

        priority = rule.get("priority")
        escalating = rule_type in ESCALATING_TYPES
        if priority is not None and priority not in VALID_PRIORITIES:
            problems.append(f"{label}: 'priority' {priority!r} must be one of {list(VALID_PRIORITIES)}")
        if escalating:
            if priority is None:
                problems.append(f"{label}: 'priority' is required for {rule_type} rules")
            route = rule.get("route")
            if not isinstance(route, str) or not route.strip():
                problems.append(f"{label}: 'route' is required for {rule_type} rules")
            elif routing_destinations is not None and route not in routing_destinations:
                problems.append(f"{label}: route {route!r} is not in routing_table.yaml")
            alert_level = rule.get("alert_level")
            if not isinstance(alert_level, str) or not alert_level.strip():
                problems.append(f"{label}: 'alert_level' is required for {rule_type} rules")
            for flag in ("human_review", "auto_reply"):
                if not isinstance(rule.get(flag), bool):
                    problems.append(f"{label}: '{flag}' must be true or false for {rule_type} rules")

    precedence = data.get("route_precedence") or []
    if not isinstance(precedence, list):
        problems.append("'route_precedence' must be a list of rule ids")
    else:
        for rule_id in precedence:
            if rule_id not in seen_ids:
                problems.append(f"route_precedence names unknown rule id {rule_id!r}")
        if len(set(precedence)) != len(precedence):
            problems.append("route_precedence contains duplicate rule ids")

    return problems


def _normalize_phrase(phrase: str) -> str:
    return _normalize_text(phrase).strip()


def _prepare_rule(rule: dict) -> dict:
    """Copy of *rule* with keywords/exclusions translated like submitted text."""
    prepared = dict(rule)
    prepared["_keywords"] = [(kw, _normalize_phrase(kw)) for kw in rule.get("keywords", [])]
    prepared["_exclusions"] = [_normalize_phrase(x) for x in rule.get("exclusions") or []]
    return prepared


def _rule_keywords(rule: dict) -> list:
    """(original, normalized) keyword pairs; tolerates rules that were not prepared."""
    if "_keywords" in rule:
        return rule["_keywords"]
    return [(kw, _normalize_phrase(kw)) for kw in rule.get("keywords", [])]


def _rule_exclusions(rule: dict) -> list:
    if "_exclusions" in rule:
        return rule["_exclusions"]
    return [_normalize_phrase(x) for x in rule.get("exclusions") or []]


def load_config() -> dict:
    """Load, validate and cache the rules. Raises ValueError listing every problem."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        data = _read_raw_config()
        problems = validate_config(data, _routing_destinations())
        if problems:
            raise ValueError(
                "Invalid sensitivity_rules.yaml:\n" + "\n".join(f" - {p}" for p in problems)
            )
        _CONFIG_CACHE = {
            "rules": [_prepare_rule(rule) for rule in data["rules"]],
            "precedence": list(data.get("route_precedence") or []),
        }
    return _CONFIG_CACHE


_load_config = load_config  # backwards-compatible name


def _load_rules() -> list:
    return load_config()["rules"]


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _phrase_pattern(phrase: str) -> re.Pattern:
    """Whole-word, case-insensitive pattern; spaces match any whitespace run."""
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    return re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)


def _phrase_in_text(phrase: str, text: str) -> bool:
    """Return True if *phrase* appears as a whole phrase in *text*."""
    return bool(_phrase_pattern(phrase).search(text))


def _exclusion_spans(text: str, exclusions: Iterable) -> list:
    """Character spans of every exclusion phrase found in *text*."""
    spans: list = []
    for phrase in exclusions or []:
        spans.extend(m.span() for m in _phrase_pattern(str(phrase)).finditer(text))
    return spans


def _overlaps(span: tuple, others: list) -> bool:
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in others)


_NEGATORS = (
    r"(?:no|not|never|without|zero|isn't|aren't|wasn't|weren't|"
    r"don't|doesn't|didn't|hasn't|haven't)"
)
# Words allowed between a negator and the keyword: "no ragging", "isn't any
# ragging", "no case of ragging". Verbs and articles are deliberately absent so
# "did not stop the ragging" and "no one stopped the ragging" stay complaints.
_FILLERS = (
    r"(?:any|such|more|a|an|single|case|cases|incident|incidents|instance|"
    r"instances|form|forms|sign|signs|kind|kinds|type|types|of)"
)
_PREFIX_NEGATION = re.compile(
    r"(?:\b" + _NEGATORS + r"\s+(?:" + _FILLERS + r"\s+){0,4}|\banti[\s-]*)$"
)
_NEGATION_WORD = (
    r"(?:(?:is|are|was|were|has|have|does|do|did|being)\s+(?:not|never)"
    r"|isn't|aren't|wasn't|weren't|hasn't|haven't|doesn't|don't|didn't|not|never)"
)
# Only an existence verb after the negation reads as "this is not occurring".
# "has not stopped" / "is not being addressed" are complaints and do not match.
# The Hinglish forms are what the cleaner leaves behind for "nahi ho rahi" / "nahi hoti".
_SUFFIX_NEGATION = re.compile(
    r"^\s*" + _NEGATION_WORD + r"\s+(?:(?:being|even)\s+)?"
    r"(?:happening|happen|happens|occurring|occur|occurs|exist|exists|existing|present|"
    r"taking\s+place|take\s+place|going\s+on|is\s+rahi|is\s+raha|is\s+rahe|"
    r"hoti|hota|hui|hua)\b"
)
# "Ragging is not happening in A block, but ..." - a contrast later in the same
# sentence means the negation cannot be trusted.
_CONTRAST = re.compile(r"\b(?:but|yet|however|although|though|still|except)\b")


def _is_negated(text: str, match: re.Match) -> bool:
    prefix = text[max(0, match.start() - 60):match.start()]
    if _PREFIX_NEGATION.search(prefix):
        return True
    suffix = text[match.end():match.end() + 60]
    if _SUFFIX_NEGATION.match(suffix):
        rest_of_sentence = re.split(r"[.!?;\n]", text[match.end():], maxsplit=1)[0]
        return not _CONTRAST.search(rest_of_sentence)
    return False


def _phrase_is_asserted(
    phrase: str,
    text: str,
    exclusion_spans: Optional[list] = None,
) -> bool:
    """
    True if *phrase* occurs at least once as a genuine, asserted mention.

    An occurrence is ignored when it overlaps one of *exclusion_spans* (the
    rule's ``exclusions`` list) or when it is clearly negated (see module
    docstring). *phrase* and *text* must already be normalised.
    """
    exclusion_spans = exclusion_spans or []
    for match in _phrase_pattern(phrase).finditer(text):
        if _overlaps(match.span(), exclusion_spans):
            continue
        if _is_negated(text, match):
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Combining the rules that fired
# ---------------------------------------------------------------------------

def _precedence_key(candidate: dict, precedence: list) -> tuple:
    """Sort key: rules listed in route_precedence first (in that order), then YAML order."""
    rule_id = candidate["rule"].get("id")
    if rule_id in precedence:
        return (0, precedence.index(rule_id))
    return (1, candidate["order"])


def _forbids_auto_reply(rule: dict) -> bool:
    """Conservative: an escalating rule that does not say auto_reply: true forbids it."""
    if rule.get("type") in ESCALATING_TYPES:
        return not rule.get("auto_reply", False)
    return rule.get("auto_reply") is False


def _most_urgent_priority(priorities: Iterable) -> Optional[str]:
    valid = [p for p in priorities if p in VALID_PRIORITIES]
    return min(valid) if valid else None  # "P1" < "P2" < "P3" < "P4"


def check_sensitivity(text: str) -> dict:
    """
    Apply all sensitivity rules to *text*.

    Returns
    -------
    dict with keys:
        is_sensitive        : bool
        sensitivity_type    : str   (NONE | SAFETY | WELFARE | MEDICAL | CONFIDENTIAL)
        matched_rule        : str   name of the primary rule (or empty string)
        matched_rule_id     : str   id of the primary rule, e.g. "R-006" (or empty string)
        matched_rule_ids    : list[str]  every rule that fired, including deadline flags:
                              the primary rule first, then other hard rules in precedence
                              order, then deadline / confidential flags. Empty only when
                              no rule fired.
        matched_keywords    : list[str]  keywords of the primary rule, as written in the YAML
        priority_override   : str | None  most urgent priority among the fired escalating rules
        route_override      : str | None  from the primary rule
        alert_level         : str | None  from the primary rule
        auto_reply_allowed  : bool  False if ANY fired rule forbids automatic replies
        needs_human_review  : bool  True if ANY fired escalating rule requires review
        evidence            : list[str]
        deadline_detected   : bool
    """
    config = load_config()
    rules = config["rules"]
    precedence = config["precedence"]
    text_norm = _normalize_text(text)

    result = {
        "is_sensitive": False,
        "sensitivity_type": "NONE",
        "matched_rule": "",
        "matched_rule_id": "",
        "matched_rule_ids": [],
        "matched_keywords": [],
        "priority_override": None,
        "route_override": None,
        "alert_level": None,
        "auto_reply_allowed": True,
        "needs_human_review": False,
        "evidence": [],
        "deadline_detected": False,
    }

    # Collect every rule that fires. Hard matches compete for the primary slot
    # by route_precedence; deadline / confidentiality flags are independent.
    hard_matches: list = []
    flags: list = []

    for order, rule in enumerate(rules):
        exclusion_spans = _exclusion_spans(text_norm, _rule_exclusions(rule))
        matched_keywords = [
            original
            for original, normalized in _rule_keywords(rule)
            if _phrase_is_asserted(normalized, text_norm, exclusion_spans)
        ]
        if not matched_keywords:
            continue

        rule_type = rule.get("type", "UNKNOWN")
        candidate = {
            "rule": rule,
            "matched_keywords": matched_keywords,
            "type": rule_type,
            "order": order,
        }
        if rule_type in HARD_SENSITIVITY_TYPES:
            hard_matches.append(candidate)
        else:
            flags.append(candidate)
            if rule_type == "DEADLINE":
                result["deadline_detected"] = True

    hard_matches.sort(key=lambda c: _precedence_key(c, precedence))

    if hard_matches:
        primary = hard_matches[0]
        others = hard_matches[1:] + flags
    else:
        primary = next((flag for flag in flags if flag["type"] == "CONFIDENTIAL"), None)
        others = [flag for flag in flags if flag is not primary]

    fired = ([primary] if primary else []) + others
    result["matched_rule_ids"] = [c["rule"].get("id", "") for c in fired]

    if fired:
        # Conservative: any fired rule that forbids auto-replies blocks them.
        result["auto_reply_allowed"] = not any(_forbids_auto_reply(c["rule"]) for c in fired)

    if primary:
        rule = primary["rule"]
        escalating = [c for c in fired if c["type"] in ESCALATING_TYPES]
        result["is_sensitive"] = True
        result["sensitivity_type"] = primary["type"]
        result["matched_rule"] = rule.get("name", "")
        result["matched_rule_id"] = rule.get("id", "")
        result["matched_keywords"] = primary["matched_keywords"]
        result["route_override"] = rule.get("route")
        result["alert_level"] = rule.get("alert_level")
        result["priority_override"] = _most_urgent_priority(
            c["rule"].get("priority") for c in escalating
        )
        result["needs_human_review"] = any(
            bool(c["rule"].get("human_review", True)) for c in escalating
        )
        result["evidence"] = [
            f"Rule {rule.get('id')} ({rule.get('name')}): "
            f"matched keywords {primary['matched_keywords']}"
        ]
        for other in others:
            result["evidence"].append(
                f"Also matched Rule {other['rule'].get('id')} "
                f"({other['rule'].get('name')}): {other['matched_keywords']}"
            )
    else:
        for flag in flags:
            result["evidence"].append(
                f"Rule {flag['rule'].get('id')} ({flag['rule'].get('name')}): "
                f"matched keywords {flag['matched_keywords']}"
            )

    # Detect deadline context even when no configured DEADLINE rule matches.
    deadline_pattern = re.compile(
        r"\b(?:deadline|due(?:\s+date)?|due\s+by|by\s+(?:today|tomorrow|this\s+week|next\s+week)|tomorrow|today|before\s+(?:end\s+of\s+day|5\s*pm|6\s*pm|11\s*:\s*59\s*(?:pm|am)))\b",
        re.IGNORECASE,
    )
    if not result["deadline_detected"] and deadline_pattern.search(text_norm):
        result["deadline_detected"] = True
        result["evidence"].append(
            "Deadline context detected; urgency considered without sensitivity escalation."
        )

    return result
