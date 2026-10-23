"""
Central triage pipeline for UniResolve AI.

Orchestrates: clean → completeness → sensitivity → ML classify →
baseline classify → priority → route → incident match → assemble result.

Configuration, data and model errors propagate to the API layer. They are
not converted into plausible-looking triage results.
"""
from typing import Optional
import re


def run_triage_pipeline(grievance_data: dict) -> dict:
    """
    Run the full AI triage pipeline on a grievance submission.

    Parameters
    ----------
    grievance_data : dict
        Keys expected (all optional except 'description'):
            description, message_type, section, hostel_block,
            course_code, event_name, urgent_deadline

    Returns
    -------
    dict with the complete analysis result.
    """
    return _run(grievance_data)


def _as_bool(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _run(grievance_data: dict) -> dict:
    from src.preprocessing.cleaner import normalize_description
    from src.preprocessing.completeness import check_completeness
    from src.rules.sensitivity_engine import check_sensitivity
    from src.classifier.predict import predict
    from src.classifier.baseline import baseline_predict
    from src.priority.scorer import compute_priority
    from src.routing.router import route_grievance
    from src.incidents.matcher import match_incident

    description: str = grievance_data.get("description", "")
    message_type: str = grievance_data.get("message_type", "Grievance")
    section: Optional[str] = grievance_data.get("section")
    hostel_block: Optional[str] = grievance_data.get("hostel_block")
    course_code: Optional[str] = grievance_data.get("course_code")
    event_name: Optional[str] = grievance_data.get("event_name")
    urgent_deadline = _as_bool(grievance_data.get("urgent_deadline", False))

    # Step 1 – Clean
    cleaned_text = normalize_description(description)

    # Step 2 – Completeness
    completeness = check_completeness(description, message_type)

    # Step 3 – Sensitivity
    sensitivity = check_sensitivity(cleaned_text)
    urgent_deadline = urgent_deadline or sensitivity.get("deadline_detected", False)

    # Step 4 – ML classification
    classifier = predict(cleaned_text)

    # Step 5 – Baseline classification
    baseline = baseline_predict(cleaned_text)
    possible_categories = baseline.get("matched_categories", [])
    multiple_issues = bool(
        re.search(
            r"\b(?:also|another issue|in addition|separately|as well as|along with)\b",
            cleaned_text,
        )
    )

    # Step 6 – Priority
    priority = compute_priority(
        sensitivity,
        completeness,
        classifier,
        urgent_deadline,
        message_type,
    )

    # Step 7 – Routing
    routing = route_grievance(classifier["predicted_subcategory"], sensitivity)

    # Step 8 – Incident matching
    incident = match_incident(
        section=section,
        course_code=course_code,
        hostel_block=hostel_block,
        event_name=event_name,
        predicted_subcategory=classifier["predicted_subcategory"],
        description=cleaned_text,
    )

    # Step 9 – Assemble final result
    needs_human_review = (
        sensitivity.get("needs_human_review", False)
        or classifier.get("needs_human_review", False)
        or not completeness.get("complete", True)
        or multiple_issues
    )

    review_reasons: list[str] = []
    if sensitivity.get("needs_human_review"):
        review_reasons.append(f"Sensitivity flag: {sensitivity.get('matched_rule')} ({sensitivity.get('sensitivity_type')})")
    if classifier.get("needs_human_review"):
        review_reasons.append(f"Low classifier confidence: {classifier.get('confidence', 0):.0%}")
    if not completeness.get("complete"):
        review_reasons.extend(completeness.get("issues", []))
    if multiple_issues:
        review_reasons.append(
            "Possible multiple issue categories: " + ", ".join(possible_categories)
        )

    model_prediction = classifier["predicted_master"]
    baseline_prediction = baseline["prediction"]
    return {
        "error": False,
        "cleaned_text": cleaned_text,
        "completeness": completeness,
        "sensitivity": sensitivity,
        "classifier": classifier,
        "baseline": baseline,
        "priority": priority,
        "routing": routing,
        "incident": incident,
        # Flat fields for easy DB storage
        "needs_human_review": needs_human_review,
        "review_reasons": review_reasons,
        "predicted_master": classifier["predicted_master"],
        "predicted_category": classifier["predicted_master"],  # alias
        "predicted_subcategory": classifier["predicted_subcategory"],
        "confidence": classifier["confidence"],
        "sensitivity_flag": sensitivity["is_sensitive"],
        "sensitivity_type": sensitivity["sensitivity_type"],
        "sensitivity_evidence": sensitivity.get("evidence", []),
        "priority_label": priority["priority_label"],
        "routed_to": routing["department"],
        "incident_id": incident.get("incident_id"),
        "baseline_prediction": baseline_prediction,
        "model_prediction": model_prediction,
        # Accuracy is measured against held-out labels in evaluation, never
        # inferred by comparing two predictions on an unlabeled submission.
        "model_wins": None,
        "top_classes": classifier.get("top_classes", []),
        "low_confidence": classifier.get("low_confidence", True),
        "classifier_explanation": classifier.get("explanation", []),
        "baseline_keywords": baseline.get("matched_keywords", []),
        "baseline_categories": possible_categories,
        "completeness_issues": completeness.get("issues", []),
        "is_complete": completeness.get("complete", False),
        "priority_score": priority.get("score", 0),
        "priority_reasons": priority.get("reasons", []),
        "routing_basis": routing.get("routing_basis", "default"),
        "incident_found": incident.get("incident_found", False),
        "incident_title": incident.get("incident_title"),
        "reply_template": incident.get("reply_template"),
        "incident_status": incident.get("incident_status"),
        "classifier_available": classifier.get("model_available", False),
        "selected_labels": {
            "master": grievance_data.get("selected_master"),
            "category": grievance_data.get("selected_category"),
            "subcategory": grievance_data.get("selected_subcategory"),
        },
    }
