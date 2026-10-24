"""
CRUD helpers for UniResolve AI.

All functions accept a SQLAlchemy Session as the first argument.
"""
import json
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import (
    AuditLog, Grievance, AIAnalysis, HumanDecision, StatusHistory, User
)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def create_user(
    db: Session,
    username: str,
    email: str,
    hashed_password: str,
    role: str = "student",
) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


# ---------------------------------------------------------------------------
# Grievances
# ---------------------------------------------------------------------------

def _generate_grievance_id() -> str:
    """Generate a unique grievance ID in GRV-YYYYMMDD-NNNNN format."""
    import random
    today = date.today().strftime("%Y%m%d")
    nonce = random.randint(10000, 99999)
    return f"GRV-{today}-{nonce}"


def create_grievance(
    db: Session,
    *,
    user_id: Optional[int],
    message_type: str,
    description: str,
    language: str = "english",
    section: Optional[str] = None,
    hostel_block: Optional[str] = None,
    course_code: Optional[str] = None,
    event_name: Optional[str] = None,
    contact_no: Optional[str] = None,
    created_by: str = "system",
    commit: bool = True,
) -> Grievance:
    # Ensure uniqueness of grievance_id
    for _ in range(10):
        gid = _generate_grievance_id()
        if not db.query(Grievance).filter(Grievance.grievance_id == gid).first():
            break

    grievance = Grievance(
        grievance_id=gid,
        user_id=user_id,
        message_type=message_type,
        description=description,
        language=language,
        section=section,
        hostel_block=hostel_block,
        course_code=course_code,
        event_name=event_name,
        contact_no=contact_no,
        status="submitted",
    )
    db.add(grievance)
    db.add(StatusHistory(
        grievance_id=gid,
        previous_status=None,
        new_status="submitted",
        changed_by=created_by,
    ))
    db.commit() if commit else db.flush()
    db.refresh(grievance)
    return grievance


def get_grievance_by_id(db: Session, grievance_id: str) -> Optional[Grievance]:
    return (
        db.query(Grievance)
        .filter(Grievance.grievance_id == grievance_id)
        .first()
    )


def get_grievances_by_user(db: Session, user_id: int) -> list:
    return (
        db.query(Grievance)
        .filter(Grievance.user_id == user_id)
        .order_by(Grievance.created_at.desc())
        .all()
    )


def get_all_grievances(db: Session, skip: int = 0, limit: int = 200) -> list:
    return (
        db.query(Grievance)
        .order_by(Grievance.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_grievance_status(
    db: Session,
    grievance_id: str,
    status: str,
    changed_by: str = "system",
    commit: bool = True,
) -> Optional[Grievance]:
    grievance = get_grievance_by_id(db, grievance_id)
    if grievance and grievance.status != status:
        previous_status = grievance.status
        grievance.status = status
        grievance.updated_at = datetime.utcnow()
        db.add(StatusHistory(
            grievance_id=grievance_id,
            previous_status=previous_status,
            new_status=status,
            changed_by=changed_by,
        ))
        db.commit() if commit else db.flush()
        db.refresh(grievance)
    return grievance


# ---------------------------------------------------------------------------
# AI Analysis
# ---------------------------------------------------------------------------

def save_ai_analysis(
    db: Session, grievance_id: str, analysis: dict, commit: bool = True
) -> AIAnalysis:
    # Remove existing if any (idempotent re-runs)
    existing = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.grievance_id == grievance_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    ai = AIAnalysis(
        grievance_id=grievance_id,
        predicted_master=analysis.get("predicted_master"),
        predicted_category=analysis.get("predicted_category"),
        predicted_subcategory=analysis.get("predicted_subcategory"),
        confidence=analysis.get("confidence"),
        sensitivity_flag=analysis.get("sensitivity_flag", False),
        sensitivity_type=analysis.get("sensitivity_type", "NONE"),
        sensitivity_evidence=json.dumps(analysis.get("sensitivity_evidence", [])),
        priority_label=analysis.get("priority_label", "P3"),
        routed_to=analysis.get("routed_to"),
        needs_human_review=analysis.get("needs_human_review", False),
        review_reasons=json.dumps(analysis.get("review_reasons", [])),
        incident_id=analysis.get("incident_id"),
        baseline_prediction=analysis.get("baseline_prediction"),
        model_prediction=analysis.get("model_prediction"),
        model_wins=analysis.get("model_wins"),
        analysis_details=json.dumps(analysis, ensure_ascii=False),
    )
    db.add(ai)
    db.commit() if commit else db.flush()
    db.refresh(ai)
    return ai


# ---------------------------------------------------------------------------
# Human Decision
# ---------------------------------------------------------------------------

def save_human_decision(
    db: Session, grievance_id: str, decision: dict, commit: bool = True
) -> HumanDecision:
    existing = (
        db.query(HumanDecision)
        .filter(HumanDecision.grievance_id == grievance_id)
        .first()
    )
    hd = existing or HumanDecision(grievance_id=grievance_id)
    hd.decided_by = decision.get("decided_by", "system")
    hd.final_category = decision.get("final_category")
    hd.final_subcategory = decision.get("final_subcategory")
    hd.final_route = decision.get("final_route")
    hd.final_priority = decision.get("final_priority")
    hd.decision_notes = decision.get("decision_notes")
    hd.resolution_solution = decision.get("resolution_solution")
    hd.decided_at = datetime.utcnow()
    if existing is None:
        db.add(hd)
    db.commit() if commit else db.flush()
    db.refresh(hd)
    return hd


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

def create_audit_log(
    db: Session,
    grievance_id: Optional[str],
    action: str,
    actor: str,
    details: Optional[dict] = None,
    commit: bool = True,
) -> AuditLog:
    log = AuditLog(
        grievance_id=grievance_id,
        action=action,
        actor=actor,
        details=json.dumps(details or {}),
    )
    db.add(log)
    db.commit() if commit else db.flush()
    db.refresh(log)
    return log


def get_pending_review_grievances(db: Session) -> list:
    """Return grievances that need human review, sorted by priority."""
    priority_order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    grievances = (
        db.query(Grievance)
        .join(AIAnalysis, Grievance.grievance_id == AIAnalysis.grievance_id)
        .filter(AIAnalysis.needs_human_review == True)  # noqa: E712
        .filter(Grievance.status == "submitted")
        .all()
    )
    return sorted(
        grievances,
        key=lambda g: priority_order.get(
            g.ai_analysis.priority_label if g.ai_analysis else "P4", 3
        ),
    )
