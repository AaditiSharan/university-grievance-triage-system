"""Student grievance submission, tracking and personal queue endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.schemas import GrievanceSubmit, GrievanceSubmitResponse
from src.api.serialization import serialize_grievance
from src.auth.dependencies import get_current_user
from src.db import crud
from src.db.connection import get_db
from src.db.models import User
from src.pipeline import run_triage_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rms", tags=["grievances"])


@router.post("/submit", response_model=GrievanceSubmitResponse, status_code=status.HTTP_201_CREATED)
def submit_grievance(
    payload: GrievanceSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        analysis = run_triage_pipeline(payload.model_dump())
        grievance = crud.create_grievance(
            db,
            user_id=current_user.id,
            message_type=payload.message_type,
            description=payload.description.strip(),
            language=payload.language,
            section=payload.section,
            hostel_block=payload.hostel_block,
            course_code=payload.course_code,
            event_name=payload.event_name,
            contact_no=payload.contact_no,
            created_by=current_user.username,
            commit=False,
        )
        crud.save_ai_analysis(db, grievance.grievance_id, analysis, commit=False)
        crud.create_audit_log(
            db,
            grievance.grievance_id,
            "SUBMIT_AND_TRIAGE",
            current_user.username,
            {
                "predicted_master": analysis["predicted_master"],
                "priority_label": analysis["priority_label"],
                "needs_human_review": analysis["needs_human_review"],
            },
            commit=False,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to submit and triage grievance for user %s", current_user.id)
        raise HTTPException(
            status_code=503,
            detail="Grievance triage or storage failed. Please retry; no submission was recorded.",
        ) from exc
    return {
        "grievance_id": grievance.grievance_id,
        "status": grievance.status,
        "message": "Submission received. AI recommendations are advisory and remain subject to human review.",
        "ai_analysis": analysis,
        "incident": analysis.get("incident"),
    }


@router.get("/track/{grievance_id}")
def track_grievance(
    grievance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    grievance = crud.get_grievance_by_id(db, grievance_id)
    if grievance is None:
        raise HTTPException(status_code=404, detail="Grievance not found.")
    if grievance.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You may only track your own submissions.")
    return serialize_grievance(grievance)


@router.get("/my-grievances")
def my_grievances(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return [
        serialize_grievance(grievance)
        for grievance in crud.get_grievances_by_user(db, current_user.id)
    ]