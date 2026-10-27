"""Tests for src/rules/sensitivity_engine.py against config/sensitivity_rules.yaml."""
import copy

import pytest
import yaml

from src.preprocessing.cleaner import normalize_description, translate_hinglish
from src.rules import sensitivity_engine
from src.rules.sensitivity_engine import HARD_SENSITIVITY_TYPES, check_sensitivity


# --- Exclusions are applied --------------------------------------------------

def test_ragging_is_flagged_when_asserted() -> None:
    result = check_sensitivity("I am facing ragging by seniors.")
    assert result["is_sensitive"] is True
    assert result["matched_rule_id"] == "R-001"
    assert result["route_override"] == "Anti-Ragging Cell"


@pytest.mark.parametrize(
    "text",
    [
        "I attended a ragging awareness workshop.",
        "Our college has an anti-ragging policy.",
        "Please share the ragging policy document.",
        "Is this a ragging free campus?",
        "There is no ragging in GH-3, but the Wi-Fi has been down.",
    ],
)
def test_ragging_mentions_covered_by_exclusions_are_not_flagged(text: str) -> None:
    result = check_sensitivity(text)
    assert result["is_sensitive"] is False
    assert result["sensitivity_type"] == "NONE"
    assert result["route_override"] is None


def test_exclusion_only_discards_the_overlapping_match() -> None:
    # The first "ragging" is excluded ("ragging awareness"); the genuine
    # complaint later in the same message must still fire the rule.
    text = "After the ragging awareness session, my seniors forced me to run laps at night."
    result = check_sensitivity(text)
    assert result["is_sensitive"] is True
    assert result["matched_rule_id"] == "R-001"
    assert "seniors forced" in result["matched_keywords"]
    assert "ragging" not in result["matched_keywords"]


def test_second_occurrence_of_same_keyword_still_counts() -> None:
    text = "Ragging awareness week starts today, but ragging is happening in my hostel."
    result = check_sensitivity(text)
    assert result["is_sensitive"] is True
    assert result["matched_rule_id"] == "R-001"


# --- route_precedence is honoured -------------------------------------------

def test_threat_takes_precedence_over_ragging() -> None:
    result = check_sensitivity("Seniors are ragging me and threatened to kill me.")
    assert result["matched_rule_id"] == "R-003"
    assert result["route_override"] == "Security & Student Welfare"
    assert result["alert_level"] == "immediate"
    assert result["matched_rule_ids"] == ["R-003", "R-001"]
    assert any("Also matched Rule R-001" in line for line in result["evidence"])


def test_self_harm_takes_precedence_over_mental_health() -> None:
    result = check_sensitivity("I am depressed and I want to die.")
    assert result["matched_rule_id"] == "R-006"
    assert result["matched_rule_ids"] == ["R-006", "R-004"]
    assert result["route_override"] == "Counselling Centre"


def test_precedence_does_not_depend_on_yaml_rule_order(monkeypatch: pytest.MonkeyPatch) -> None:
    config = sensitivity_engine._load_config()
    reordered = {
        "rules": list(reversed(config["rules"])),
        "precedence": config["precedence"],
    }
    monkeypatch.setattr(sensitivity_engine, "_CONFIG_CACHE", reordered)
    result = check_sensitivity("Seniors are ragging me and threatened to kill me.")
    assert result["matched_rule_id"] == "R-003"


# --- WELFARE rules (R-004 / R-006) now escalate -----------------------------

@pytest.mark.parametrize(
    ("text", "rule_id", "alert_level"),
    [
        ("I want to die.", "R-006", "immediate"),
        ("I have been thinking about suicide.", "R-006", "immediate"),
        ("I feel hopeless and depressed.", "R-004", "urgent"),
    ],
)
def test_welfare_rules_are_treated_as_sensitive(text: str, rule_id: str, alert_level: str) -> None:
    result = check_sensitivity(text)
    assert result["is_sensitive"] is True
    assert result["sensitivity_type"] == "WELFARE"
    assert result["matched_rule_id"] == rule_id
    assert result["priority_override"] == "P1"
    assert result["route_override"] == "Counselling Centre"
    assert result["needs_human_review"] is True
    assert result["alert_level"] == alert_level


@pytest.mark.parametrize(
    "text",
    ["I am dying of boredom in this lecture.", "I will die of embarrassment if I fail."],
)
def test_figures_of_speech_are_not_self_harm(text: str) -> None:
    assert check_sensitivity(text)["is_sensitive"] is False


# --- Returned policy fields -------------------------------------------------

def test_auto_reply_and_alert_level_come_from_the_rule() -> None:
    result = check_sensitivity("I want to die.")
    assert result["auto_reply_allowed"] is False
    assert result["alert_level"] == "immediate"

    quiet = check_sensitivity("The Wi-Fi in my hostel is slow.")
    assert quiet["is_sensitive"] is False
    assert quiet["alert_level"] is None
    assert quiet["auto_reply_allowed"] is True


# --- Config consistency -----------------------------------------------------

def test_every_rule_type_is_a_hard_sensitivity_type() -> None:
    """Catches a YAML rule type the engine would silently treat as non-sensitive."""
    for rule in sensitivity_engine._load_rules():
        assert rule["type"] in HARD_SENSITIVITY_TYPES, (
            f"{rule['id']} has type {rule['type']!r}, which the engine would not escalate"
        )


def test_route_precedence_lists_every_rule_exactly_once() -> None:
    config = sensitivity_engine._load_config()
    rule_ids = sorted(rule["id"] for rule in config["rules"])
    assert sorted(config["precedence"]) == rule_ids


def test_every_rule_route_exists_in_routing_table() -> None:
    from pathlib import Path

    routing_path = Path(sensitivity_engine.BASE_DIR) / "config" / "routing_table.yaml"
    routing_text = routing_path.read_text(encoding="utf-8-sig")
    for rule in sensitivity_engine._load_rules():
        assert rule["route"] in routing_text, f"{rule['id']} routes to unknown office {rule['route']!r}"


# --- End to end through the pipeline ----------------------------------------

def test_self_harm_message_is_p1_and_routed_to_counselling() -> None:
    from src.pipeline import run_triage_pipeline

    result = run_triage_pipeline({"description": "I do not want to live anymore, I want to die."})
    assert result["sensitivity_flag"] is True
    assert result["sensitivity_type"] == "WELFARE"
    assert result["priority_label"] == "P1"
    assert result["routed_to"] == "Counselling Centre"
    assert result["needs_human_review"] is True


# --- CONFIDENTIAL-only branch ------------------------------------------------

def test_confidential_only_match_carries_priority_and_route(monkeypatch: pytest.MonkeyPatch) -> None:
    config = sensitivity_engine._load_config()
    confidential_rule = {
        "id": "R-900",
        "name": "Confidential request",
        "type": "CONFIDENTIAL",
        "priority": "P1",
        "alert_level": "urgent",
        "route": "Student Welfare",
        "human_review": True,
        "auto_reply": False,
        "keywords": ["please keep this confidential"],
        "exclusions": [],
    }
    patched = {"rules": config["rules"] + [confidential_rule], "precedence": config["precedence"]}
    monkeypatch.setattr(sensitivity_engine, "_CONFIG_CACHE", patched)

    result = check_sensitivity("The hostel warden was rude, please keep this confidential.")
    assert result["is_sensitive"] is True
    assert result["sensitivity_type"] == "CONFIDENTIAL"
    assert result["matched_rule_id"] == "R-900"
    assert result["matched_rule_ids"] == ["R-900"]
    assert result["priority_override"] == "P1"
    assert result["route_override"] == "Student Welfare"
    assert result["auto_reply_allowed"] is False

    from src.priority.scorer import compute_priority

    priority = compute_priority(result, {"complete": True}, {"low_confidence": False})
    assert priority["priority_label"] == "P1"


# --- Scorer policy ----------------------------------------------------------

def test_incomplete_description_is_p3_not_p4() -> None:
    from src.priority.scorer import compute_priority

    result = compute_priority(
        check_sensitivity("ok asap"),
        {"complete": False, "issues": ["Too short"]},
        {"low_confidence": True, "confidence": 0.1, "predicted_master": "UNCLEAR"},
    )
    assert result["priority_label"] == "P3"


def test_compute_priority_needs_the_explicit_deadline_flag() -> None:
    from src.priority.scorer import compute_priority

    sens = check_sensitivity("Fee deadline is tomorrow.")
    complete = {"complete": True}
    clf = {"low_confidence": False, "confidence": 0.9, "predicted_master": "Fees"}
    assert compute_priority(sens, complete, clf)["priority_label"] == "P3"
    assert compute_priority(sens, complete, clf, urgent_deadline=True)["priority_label"] == "P2"


def test_matched_rule_ids_is_consistent_with_matched_rule_id(monkeypatch: pytest.MonkeyPatch) -> None:
    config = sensitivity_engine._load_config()
    confidential_rule = {
        "id": "R-900", "name": "Confidential request", "type": "CONFIDENTIAL",
        "priority": "P1", "route": "Student Welfare", "human_review": True,
        "auto_reply": False, "keywords": ["please keep this confidential"], "exclusions": [],
    }
    monkeypatch.setattr(
        sensitivity_engine, "_CONFIG_CACHE",
        {"rules": config["rules"] + [confidential_rule], "precedence": config["precedence"]},
    )

    # Hard rule + confidentiality request: the hard rule leads, both are listed.
    both = check_sensitivity("Seniors are ragging me, please keep this confidential.")
    assert both["matched_rule_id"] == "R-001"
    assert both["matched_rule_ids"] == ["R-001", "R-900"]

    # Nothing fired: both are empty together.
    none = check_sensitivity("The Wi-Fi in my hostel is slow.")
    assert none["matched_rule_id"] == ""
    assert none["matched_rule_ids"] == []

    # Whenever a rule is reported, it is the first entry in the list.
    for text in ("I want to die.", "Seniors are ragging me and threatened to kill me."):
        result = check_sensitivity(text)
        assert result["matched_rule_ids"][0] == result["matched_rule_id"]


# ---------------------------------------------------------------------------
# Helpers for tests that need a custom rule set
# ---------------------------------------------------------------------------

def _rule(rule_id: str, rule_type: str, keywords: list, **overrides) -> dict:
    rule = {
        "id": rule_id, "name": f"Rule {rule_id}", "type": rule_type, "priority": "P1",
        "alert_level": "immediate", "route": "Security & Student Welfare",
        "human_review": True, "auto_reply": False, "keywords": keywords, "exclusions": [],
    }
    rule.update(overrides)
    return rule


def _use_rules(monkeypatch: pytest.MonkeyPatch, rules: list, precedence: list) -> None:
    monkeypatch.setattr(
        sensitivity_engine, "_CONFIG_CACHE", {"rules": rules, "precedence": precedence}
    )


def _triage(text: str) -> dict:
    """Run text through the same cleaning step the pipeline uses, then the engine."""
    return check_sensitivity(normalize_description(text))


# ---------------------------------------------------------------------------
# Policy flags are combined across every fired rule
# ---------------------------------------------------------------------------

def test_any_fired_rule_that_forbids_auto_reply_blocks_it(monkeypatch: pytest.MonkeyPatch) -> None:
    permissive = _rule(
        "A-1", "SAFETY", ["alpha"], auto_reply=True, human_review=False,
        priority="P2", alert_level="urgent", route="Counselling Centre",
    )
    strict = _rule("B-1", "WELFARE", ["bravo"])  # auto_reply false, human review, P1
    _use_rules(monkeypatch, [permissive, strict], ["A-1", "B-1"])

    only_permissive = check_sensitivity("alpha")
    assert only_permissive["auto_reply_allowed"] is True
    assert only_permissive["needs_human_review"] is False
    assert only_permissive["priority_override"] == "P2"

    both = check_sensitivity("alpha and bravo")
    assert both["matched_rule_id"] == "A-1"  # primary by route_precedence
    assert both["auto_reply_allowed"] is False  # B-1 forbids it
    assert both["needs_human_review"] is True  # B-1 requires it
    assert both["priority_override"] == "P1"  # most urgent of P2 and P1
    # Route and alert level still come from the primary rule, as documented.
    assert both["route_override"] == "Counselling Centre"
    assert both["alert_level"] == "urgent"


def test_escalating_rule_without_auto_reply_flag_is_treated_as_forbidding_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = _rule("A-1", "SAFETY", ["alpha"])
    del rule["auto_reply"]
    _use_rules(monkeypatch, [rule], ["A-1"])
    assert check_sensitivity("alpha")["auto_reply_allowed"] is False


# ---------------------------------------------------------------------------
# matched_rule_ids covers deadline-only matches
# ---------------------------------------------------------------------------

def test_deadline_only_match_is_listed_but_not_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    deadline = {"id": "D-1", "name": "Deadline", "type": "DEADLINE", "keywords": ["deadline is tomorrow"]}
    _use_rules(monkeypatch, [deadline], [])

    result = check_sensitivity("My fee deadline is tomorrow.")
    assert result["is_sensitive"] is False
    assert result["matched_rule_id"] == ""  # no sensitivity-establishing rule
    assert result["matched_rule_ids"] == ["D-1"]  # but the rule did fire
    assert result["deadline_detected"] is True
    assert result["auto_reply_allowed"] is True
    assert result["needs_human_review"] is False
    assert any("D-1" in line for line in result["evidence"])

    # A deadline rule that explicitly forbids auto-replies still blocks them.
    deadline["auto_reply"] = False
    assert check_sensitivity("My fee deadline is tomorrow.")["auto_reply_allowed"] is False


# ---------------------------------------------------------------------------
# Negation: realistic complaints versus realistic negations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "The warden did not stop the ragging.",
        "No one stopped the ragging in our hostel.",
        "I don't think the harassment stopped.",
        "Harassment is not being addressed by the department.",
        "Ragging has not stopped even after I complained.",
        "Nobody is doing anything about the ragging.",
        "Ragging is not happening in A block, but it is in B block.",
        "Ragging awareness week started, yet ragging continues in my hostel.",
    ],
)
def test_complaints_that_contain_a_negation_are_still_flagged(text: str) -> None:
    assert check_sensitivity(text)["is_sensitive"] is True


@pytest.mark.parametrize(
    "text",
    [
        "There is no ragging in our hostel.",
        "There isn't any ragging in our hostel.",
        "There have been no cases of ragging this year.",
        "Ragging is not happening in our block.",
        "We are an anti-ragging campus.",
        "Our hostel is ragging-free.",
    ],
)
def test_clear_negations_are_not_flagged(text: str) -> None:
    assert check_sensitivity(text)["is_sensitive"] is False


@pytest.mark.parametrize(
    "text",
    [
        "I have never seen any ragging here.",  # clear to a person, not to a regex
        "Ragging is not allowed on campus, as the policy says.",
    ],
)
def test_negations_the_engine_cannot_read_are_flagged_for_review(text: str) -> None:
    """Documented limitation: when unsure, flag for a human rather than ignore."""
    assert check_sensitivity(text)["is_sensitive"] is True


# ---------------------------------------------------------------------------
# Hinglish (through the same cleaning step the pipeline applies)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("text", "rule_id"),
    [
        ("Seniors ne dhamki di hai", "R-001"),
        ("Mere dost ne khud ko nuksaan pahunchaya hai", "R-006"),
        ("Mujhe maarne ki dhamki mil rahi hai", "R-003"),
        ("Mujhe suicide ke vichar aa rahe hain", "R-006"),
        ("mujhe depression hai aur jeene ka mann nahi karta", "R-004"),
        ("Mujhe chhedkhani ka saamna karna pad raha hai", "R-002"),
        ("Warden ragging rok nahi raha, roz ragging hoti hai", "R-001"),
    ],
)
def test_hinglish_complaints_are_flagged(text: str, rule_id: str) -> None:
    result = _triage(text)
    assert result["is_sensitive"] is True
    assert rule_id in result["matched_rule_ids"]
    assert result["priority_override"] == "P1"


@pytest.mark.parametrize(
    "text",
    ["Hostel mein ragging nahi hoti hai", "Hostel mein ragging nahi ho rahi hai"],
)
def test_hinglish_negations_are_not_flagged(text: str) -> None:
    assert _triage(text)["is_sensitive"] is False


def test_every_yaml_keyword_still_matches_after_cleaning() -> None:
    """A keyword the cleaner rewrites (e.g. 'dhamki' -> 'threat') must still be reachable."""
    for rule in sensitivity_engine._load_rules():
        for keyword, normalized in sensitivity_engine._rule_keywords(rule):
            cleaned = normalize_description(keyword)
            assert sensitivity_engine._phrase_in_text(normalized, cleaned), (
                f"{rule['id']} keyword {keyword!r} cannot match cleaned text {cleaned!r}"
            )


def test_hinglish_translation_is_idempotent() -> None:
    samples = ["seniors ne dhamki di aur khud ko nuksaan", "main bahut pareshan hoon", "ragging nahi hoti hai"]
    for rule in sensitivity_engine._load_rules():
        samples.extend(rule["keywords"])
        samples.extend(rule.get("exclusions") or [])
    for sample in samples:
        once = translate_hinglish(sample.lower())
        assert translate_hinglish(once) == once, sample


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

def _raw_config() -> dict:
    return copy.deepcopy(sensitivity_engine._read_raw_config())


def test_shipped_configuration_is_valid() -> None:
    destinations = sensitivity_engine._routing_destinations()
    assert sensitivity_engine.validate_config(_raw_config(), destinations) == []


def _drop(rule_index: int, key: str):
    def mutate(data: dict) -> None:
        del data["rules"][rule_index][key]
    return mutate


def _set(rule_index: int, key: str, value):
    def mutate(data: dict) -> None:
        data["rules"][rule_index][key] = value
    return mutate


def _duplicate_id(data: dict) -> None:
    data["rules"][1]["id"] = data["rules"][0]["id"]


def _unknown_precedence(data: dict) -> None:
    data["route_precedence"].append("R-999")


def _repeated_precedence(data: dict) -> None:
    data["route_precedence"].append(data["route_precedence"][0])


def _no_rules(data: dict) -> None:
    data["rules"] = []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_duplicate_id, "duplicate rule id"),
        (_set(0, "type", "BOGUS"), "type 'BOGUS'"),
        (_set(0, "priority", "P9"), "'priority' 'P9'"),
        (_drop(0, "priority"), "'priority' is required"),
        (_drop(0, "keywords"), "'keywords'"),
        (_set(0, "keywords", []), "'keywords'"),
        (_set(0, "route", "Nowhere Office"), "not in routing_table.yaml"),
        (_drop(0, "route"), "'route' is required"),
        (_drop(0, "alert_level"), "'alert_level' is required"),
        (_drop(0, "auto_reply"), "'auto_reply'"),
        (_set(0, "human_review", "yes"), "'human_review'"),
        (_set(0, "exclusions", "ragging policy"), "'exclusions'"),
        (_unknown_precedence, "unknown rule id 'R-999'"),
        (_repeated_precedence, "duplicate rule ids"),
        (_no_rules, "non-empty list"),
    ],
)
def test_validate_config_reports_problems(mutate, expected: str) -> None:
    data = _raw_config()
    mutate(data)
    problems = sensitivity_engine.validate_config(data, sensitivity_engine._routing_destinations())
    assert any(expected in problem for problem in problems), problems


def test_load_config_refuses_an_invalid_rules_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    real_config = sensitivity_engine.BASE_DIR / "config"
    (config_dir / "routing_table.yaml").write_text(
        (real_config / "routing_table.yaml").read_text(encoding="utf-8-sig"), encoding="utf-8"
    )
    data = _raw_config()
    data["rules"][0]["priority"] = "P9"
    (config_dir / "sensitivity_rules.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    monkeypatch.setattr(sensitivity_engine, "BASE_DIR", tmp_path)
    monkeypatch.setattr(sensitivity_engine, "_CONFIG_CACHE", None)
    with pytest.raises(ValueError, match="Invalid sensitivity_rules.yaml"):
        sensitivity_engine.load_config()


def test_hinglish_self_harm_report_is_p1_through_the_pipeline() -> None:
    """The most frequently missed dataset sentence before Hinglish keywords were normalised."""
    from src.pipeline import run_triage_pipeline

    result = run_triage_pipeline(
        {"description": "Mere dost ne khud ko nuksaan pahunchaya hai, please counsellor ko bhejiye."}
    )
    assert result["sensitivity_flag"] is True
    assert result["priority_label"] == "P1"
    assert result["routed_to"] == "Counselling Centre"
    assert result["needs_human_review"] is True