"""
Audit logger for UniResolve AI.

Thin wrapper that writes to the AuditLog database table.
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from src.db.crud import create_audit_log


def log_action(
    db: Session,
    grievance_id: Optional[str],
    action: str,
    actor: str,
    details: Optional[dict] = None,
) -> None:
    """
    Persist an audit event to the database.

    Parameters
    ----------
    db           : SQLAlchemy session
    grievance_id : Grievance public ID (or None for system-level actions)
    action       : Short action label, e.g. "SUBMIT", "AI_TRIAGE", "HUMAN_DECIDE"
    actor        : Username or "system"
    details      : Arbitrary JSON-serialisable dict
    """
    try:
        create_audit_log(
            db=db,
            grievance_id=grievance_id,
            action=action,
            actor=actor,
            details=details or {},
        )
    except Exception as exc:
        # Audit logging must never crash the main flow
        import logging
        logging.getLogger(__name__).error(
            "Failed to write audit log: %s | action=%s grievance=%s",
            exc,
            action,
            grievance_id,
        )
