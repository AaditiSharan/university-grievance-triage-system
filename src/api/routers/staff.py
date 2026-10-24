"""Department-scoped staff and faculty grievance workflows."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas import BulkDecisionSubmit, DraftRequest, HumanDecisionSubmit
from src.api.serialization import serialize_grievance
from src.auth.dependencies import get_current_user
from src.db import crud
from src.db.connection import get_db
from src.db.models import User

router = APIRouter(prefix="/rms/staff", tags=["staff"])


def _can_view(grievance, user: User) -> bool:
    if user.role == "admin":
        return True
    department = (user.department or "").strip().casefold()
    routed_to = (grievance.ai_analysis.routed_to or "").strip().casefold() if grievance.ai_analysis else ""
    return bool(department and routed_to and department == routed_to)


def _require_staff(user: User) -> None:
    if user.role not in {"staff", "admin"}:
        raise HTTPException(status_code=403, detail="Staff review permissions are required.")


def _get_authorized_grievance(db: Session, grievance_id: str, user: User):
    grievance = crud.get_grievance_by_id(db, grievance_id)
    if grievance is None:
        raise HTTPException(status_code=404, detail="Grievance not found.")
    if not _can_view(grievance, user):
        raise HTTPException(status_code=403, detail="This grievance is outside your authorized department.")
    return grievance


def _save_decision(db: Session, grievance, payload: HumanDecisionSubmit, user: User) -> None:
    if payload.new_status in {"resolved", "closed"} and not (payload.resolution_solution or "").strip():
        raise HTTPException(
            status_code=422,
            detail="A staff-written resolution solution is required to resolve or close a grievance.",
        )
    previous_decision = grievance.human_decision
    crud.save_human_decision(
        db,
        grievance.grievance_id,
        {
            "decided_by": user.username,
            "final_category": payload.final_category,
            "final_subcategory": payload.final_subcategory,
            "final_route": payload.final_route,
            "final_priority": payload.final_priority,
            "decision_notes": payload.decision_notes,
            "resolution_solution": payload.resolution_solution,
        },
        commit=False,
    )
    crud.update_grievance_status(
        db, grievance.grievance_id, payload.new_status, changed_by=user.username, commit=False
    )
    crud.create_audit_log(
        db,
        grievance.grievance_id,
        "HUMAN_REVIEW_EDITED" if previous_decision else "HUMAN_REVIEW_APPROVED",
        user.username,
        {
            "new_status": payload.new_status,
            "final_category": payload.final_category,
            "final_subcategory": payload.final_subcategory,
            "final_route": payload.final_route,
            "final_priority": payload.final_priority,
            "decision_notes": payload.decision_notes,
            "resolution_solution": payload.resolution_solution,
        },
        commit=False,
    )


@router.get("/grievances")
def list_department_grievances(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    if user.role not in {"faculty", "staff", "admin"}:
        raise HTTPException(status_code=403, detail="Faculty or staff access is required.")
    grievances = crud.get_all_grievances(db, limit=1000)
    return [
        serialize_grievance(item, include_audit=True)
        for item in grievances if _can_view(item, user)
    ]


@router.get("/stats")
def department_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role not in {"faculty", "staff", "admin"}:
        raise HTTPException(status_code=403, detail="Faculty or staff access is required.")
    grievances = [
        item for item in crud.get_all_grievances(db, limit=1000)
        if _can_view(item, user)
    ]
    return {
        "total": len(grievances),
        "by_status": dict(Counter(item.status for item in grievances)),
        "pending_review": sum(
            bool(item.ai_analysis and item.ai_analysis.needs_human_review)
            and item.human_decision is None for item in grievances
        ),
        "sensitive_count": sum(
            bool(
                item.ai_analysis
                and (
                    item.ai_analysis.sensitivity_flag
                    or (item.ai_analysis.sensitivity_type or "NONE").upper() not in {"", "NONE"}
                )
            )
            for item in grievances
        ),
    }


@router.post("/draft-resolutions")
def draft_resolutions(
    payload: DraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    _require_staff(user)
    drafts = []
    for grievance_id in payload.grievance_ids:
        grievance = _get_authorized_grievance(db, grievance_id, user)
        analysis = grievance.ai_analysis
        if analysis is None:
            raise HTTPException(status_code=409, detail=f"{grievance_id} has no triage analysis.")
        if analysis.sensitivity_flag or (analysis.sensitivity_type or "NONE").upper() not in {"", "NONE"}:
            raise HTTPException(
                status_code=403,
                detail=f"AI drafting is prohibited for sensitive grievance {grievance_id}; assign human handling.",
            )
        category = analysis.predicted_subcategory or analysis.predicted_category or analysis.predicted_master or "your concern"
        department = analysis.routed_to or user.department or "the responsible department"
        draft = (
            f"Thank you for contacting {department} about {category}. "
            "We have reviewed the information provided and will follow up with the appropriate next steps. "
            "Please reply if there are relevant details you would like the assigned staff member to consider."
        )
        crud.create_audit_log(
            db, grievance_id, "AI_RESOLUTION_DRAFT_REQUESTED", user.username,
            {"draft_source": "local_triage_context", "drafted_text": draft}, commit=False,
        )
        drafts.append({"grievance_id": grievance_id, "draft": draft, "requires_individual_review": True})
    db.commit()
    return {"drafts": drafts, "saved_or_sent": False}


@router.post("/review/{grievance_id}")
def review_grievance(
    grievance_id: str,
    payload: HumanDecisionSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    _require_staff(user)
    grievance = _get_authorized_grievance(db, grievance_id, user)
    try:
        _save_decision(db, grievance, payload, user)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(grievance)
    return serialize_grievance(grievance, include_audit=True)


@router.post("/bulk-review")
def bulk_review(
    payload: BulkDecisionSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    _require_staff(user)
    grievances = [
        _get_authorized_grievance(db, item.grievance_id, user)
        for item in payload.items
    ]
    try:
        for grievance, item in zip(grievances, payload.items):
            _save_decision(db, grievance, item, user)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "updated": [
            serialize_grievance(
                crud.get_grievance_by_id(db, item.grievance_id), include_audit=True
            )
            for item in payload.items
        ],
        "count": len(payload.items),
    }
