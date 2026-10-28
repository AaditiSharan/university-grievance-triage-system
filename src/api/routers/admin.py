"""Administrator review queue and human decision endpoints."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas import HumanDecisionSubmit
from src.api.serialization import serialize_grievance
from src.auth.dependencies import require_admin
from src.db import crud
from src.db.connection import get_db
from src.db.models import User

router = APIRouter(prefix="/rms/admin", tags=["admin"])


@router.get("/grievances")
def get_grievances(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[dict]:
    return [
        serialize_grievance(grievance, include_audit=True)
        for grievance in crud.get_all_grievances(db, limit=1000)
    ]


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    grievances = crud.get_all_grievances(db, limit=10000)
    by_status = Counter(grievance.status for grievance in grievances)
    by_priority: Counter[str] = Counter()
    by_master_category: Counter[str] = Counter()
    pending_review = 0
    sensitive_count = 0
    for grievance in grievances:
        analysis = grievance.ai_analysis
        if analysis is None:
            continue
        by_priority[analysis.priority_label or "P3"] += 1
        by_master_category[analysis.predicted_master or "UNCLEAR"] += 1
        sensitive_count += int(
            bool(analysis.sensitivity_flag)
            or (analysis.sensitivity_type or "NONE").upper() not in {"", "NONE"}
        )
        pending_review += int(
            bool(analysis.needs_human_review) and grievance.human_decision is None
        )
    return {
        "total": len(grievances),
        "by_status": dict(by_status),
        "by_priority": dict(by_priority),
        "by_master_category": dict(by_master_category),
        "pending_review": pending_review,
        "sensitive_count": sensitive_count,
    }


@router.post("/review/{grievance_id}")
def review_grievance(
    grievance_id: str,
    payload: HumanDecisionSubmit,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    grievance = crud.get_grievance_by_id(db, grievance_id)
    if grievance is None:
        raise HTTPException(status_code=404, detail="Grievance not found.")
    try:
        previous_decision = grievance.human_decision
        crud.save_human_decision(
            db,
            grievance_id,
            {
                "decided_by": admin.username,
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
            db, grievance_id, payload.new_status, changed_by=admin.username, commit=False
        )
        crud.create_audit_log(
            db,
            grievance_id,
            "HUMAN_REVIEW_EDITED" if previous_decision else "HUMAN_REVIEW_APPROVED",
            admin.username,
            {
                "new_status": payload.new_status,
                "final_category": payload.final_category,
                "final_subcategory": payload.final_subcategory,
                "final_route": payload.final_route,
                "final_priority": payload.final_priority,
            },
            commit=False,
        )
        db.commit()
    except crud.FinalizedDecisionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(grievance)
    return serialize_grievance(grievance, include_audit=True)