"""Serialize persisted triage and review records for API consumers."""
import json
from typing import Any

from src.db.models import Grievance


def _decode_details(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    decoded = json.loads(value)
    return decoded if isinstance(decoded, dict) else {}


def serialize_grievance(grievance: Grievance, *, include_audit: bool = False) -> dict[str, Any]:
    analysis = grievance.ai_analysis
    details = _decode_details(analysis.analysis_details if analysis else None)
    if analysis and not details:
        details = {
            "predicted_master": analysis.predicted_master,
            "predicted_category": analysis.predicted_category,
            "predicted_subcategory": analysis.predicted_subcategory,
            "confidence": analysis.confidence or 0.0,
            "sensitivity_flag": analysis.sensitivity_flag,
            "sensitivity_type": analysis.sensitivity_type,
            "sensitivity_evidence": json.loads(analysis.sensitivity_evidence or "[]"),
            "priority_label": analysis.priority_label,
            "routed_to": analysis.routed_to,
            "needs_human_review": analysis.needs_human_review,
            "review_reasons": json.loads(analysis.review_reasons or "[]"),
            "incident_id": analysis.incident_id,
            "baseline_prediction": analysis.baseline_prediction,
            "model_prediction": analysis.model_prediction,
            "model_wins": analysis.model_wins,
        }
    result = {
        "grievance_id": grievance.grievance_id,
        "message_type": grievance.message_type,
        "description": grievance.description,
        "language": grievance.language,
        "section": grievance.section,
        "hostel_block": grievance.hostel_block,
        "course_code": grievance.course_code,
        "event_name": grievance.event_name,
        "contact_no": grievance.contact_no,
        "status": grievance.status,
        "created_at": grievance.created_at,
        "updated_at": grievance.updated_at,
        "ai_analysis": details or None,
        "human_decision": None,
    }
    if grievance.human_decision:
        decision = grievance.human_decision
        result["human_decision"] = {
            "decided_by": decision.decided_by,
            "final_category": decision.final_category,
            "final_subcategory": decision.final_subcategory,
            "final_route": decision.final_route,
            "final_priority": decision.final_priority,
            "decision_notes": decision.decision_notes,
            "resolution_solution": decision.resolution_solution,
            "decided_at": decision.decided_at,
        }
    result["status_history"] = [
        {
            "previous_status": event.previous_status,
            "new_status": event.new_status,
            "changed_by": event.changed_by,
            "changed_at": event.changed_at,
        }
        for event in grievance.status_history
    ]
    if include_audit:
        result["audit_events"] = [
            {
                "action": event.action,
                "actor": event.actor,
                "details": _decode_details(event.details),
                "timestamp": event.timestamp,
            }
            for event in grievance.audit_logs
        ]
    return result
