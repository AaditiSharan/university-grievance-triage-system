"""The reviewer-facing evidence must stay readable whichever vectorizer is loaded."""
from src.classifier.predict import _evidence_word
from src.pipeline import run_triage_pipeline


def test_evidence_word_hides_character_ngrams_and_strips_prefix() -> None:
    assert _evidence_word("c__ fee") is None
    assert _evidence_word("w__fee payment") == "fee payment"
    assert _evidence_word("fee payment") == "fee payment"  # older, non-union vectorizer


def test_pipeline_explanation_contains_only_readable_words() -> None:
    result = run_triage_pipeline({"description": "Mera fee payment UMS me show nahi ho raha hai"})
    evidence = result["classifier_explanation"]
    assert evidence, "expected some evidence words"
    assert all("__" not in word and word == word.strip() for word in evidence)