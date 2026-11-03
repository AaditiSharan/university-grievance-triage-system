"""
Firestore storage backend for UniResolve AI.

Enabled with DB_BACKEND=firestore. Mirrors the CRUD helpers in src/db/crud.py
and returns lightweight records exposing the same attributes as the SQLAlchemy
models, so routers and serialization work unchanged.

Layout:
  users/{u_<username>}          one document per user
  counters/users                integer id sequence for users
  grievances/{grievance_id}     grievance fields plus nested ai_analysis,
                                human_decision, status_history and audit_logs
  audit_logs/{auto}             audit events not tied to a grievance
"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

USERS = "users"
GRIEVANCES = "grievances"
COUNTERS = "counters"
AUDIT_LOGS = "audit_logs"

_client = None


def get_client():
    global _client
    if _client is None:
        from google.cloud import firestore

        project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("FIRESTORE_PROJECT_ID")
        _client = firestore.Client(project=project) if project else firestore.Client()
    return _client


def _now() -> datetime:
    return datetime.utcnow()


def _to_naive_utc(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _plain(value: Any) -> Any:
    """Convert values (e.g. numpy scalars) into Firestore-compatible Python types."""
    if value is None or isinstance(value, (str, bool, int, float, datetime)):
        return value
    return json.loads(json.dumps(value, default=lambda item: item.item() if hasattr(item, "item") else str(item)))


class Record:
    """Read-only attribute view over a Firestore map; missing fields read as None."""

    def __init__(self, data: Optional[dict] = None):
        object.__setattr__(self, "_data", dict(data or {}))

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return _to_naive_utc(self._data.get(name))

    def __setattr__(self, name: str, value: Any) -> None:
        self._data[name] = value

    def to_dict(self) -> dict:
        return dict(self._data)


class FirestoreGrievance(Record):
    @property
    def ai_analysis(self) -> Optional[Record]:
        data = self._data.get("ai_analysis")
        return Record(data) if data else None

    @property
    def human_decision(self) -> Optional[Record]:
        data = self._data.get("human_decision")
        return Record(data) if data else None

    @property
    def status_history(self) -> list[Record]:
        events = [Record(item) for item in self._data.get("status_history") or []]
        return sorted(events, key=lambda event: event.changed_at or datetime.min)

    @property
    def audit_logs(self) -> list[Record]:
        events = [Record(item) for item in self._data.get("audit_logs") or []]
        return sorted(events, key=lambda event: event.timestamp or datetime.min)


class FirestoreSession:
    """Unit of work with the commit/rollback/refresh surface the routers use."""

    def __init__(self, client=None):
        self.client = client or get_client()
        self._grievances: dict[str, FirestoreGrievance] = {}
        self._new: set[str] = set()
        self._changed: dict[str, set[str]] = {}
        self._appended: dict[str, dict[str, list]] = {}
        self._loose_audit: list[dict] = []

    # -- unit of work -------------------------------------------------------
    def _set(self, grievance: FirestoreGrievance, field: str, value: Any) -> None:
        grievance._data[field] = value
        self._changed.setdefault(grievance.grievance_id, set()).add(field)

    def _append(self, grievance: FirestoreGrievance, field: str, item: dict) -> None:
        grievance._data.setdefault(field, [])
        grievance._data[field] = list(grievance._data[field]) + [item]
        self._appended.setdefault(grievance.grievance_id, {}).setdefault(field, []).append(item)

    def _remember(self, grievance: FirestoreGrievance) -> FirestoreGrievance:
        return self._grievances.setdefault(grievance.grievance_id, grievance)

    def commit(self) -> None:
        from google.cloud import firestore

        batch = self.client.batch()
        writes = 0
        collection = self.client.collection(GRIEVANCES)
        for gid, grievance in self._grievances.items():
            ref = collection.document(gid)
            if gid in self._new:
                batch.create(ref, grievance.to_dict())
                writes += 1
                continue
            update = {field: grievance._data.get(field) for field in self._changed.get(gid, set())}
            for field, items in self._appended.get(gid, {}).items():
                update[field] = firestore.ArrayUnion(items)
            if update:
                batch.update(ref, update)
                writes += 1
        for entry in self._loose_audit:
            batch.set(self.client.collection(AUDIT_LOGS).document(), entry)
            writes += 1
        if writes:
            batch.commit()
        self._new.clear()
        self._changed.clear()
        self._appended.clear()
        self._loose_audit.clear()

    def flush(self) -> None:
        """Writes are buffered until commit(); nothing to flush."""

    def rollback(self) -> None:
        self._grievances.clear()
        self._new.clear()
        self._changed.clear()
        self._appended.clear()
        self._loose_audit.clear()

    def refresh(self, obj: Any) -> None:
        if isinstance(obj, FirestoreGrievance) and obj.grievance_id not in self._new:
            snapshot = self.client.collection(GRIEVANCES).document(obj.grievance_id).get()
            if snapshot.exists:
                obj._data.clear()
                obj._data.update(snapshot.to_dict())

    def close(self) -> None:
        self.rollback()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def _user_doc_id(username: str) -> str:
    return "u_" + quote(username, safe="")


def _next_user_id(client) -> int:
    from google.cloud import firestore

    ref = client.collection(COUNTERS).document(USERS)

    @firestore.transactional
    def increment(transaction) -> int:
        snapshot = ref.get(transaction=transaction)
        value = int((snapshot.to_dict() or {}).get("value", 0)) + 1 if snapshot.exists else 1
        transaction.set(ref, {"value": value})
        return value

    return increment(client.transaction())


def create_user(
    db: FirestoreSession,
    username: str,
    email: str,
    hashed_password: str,
    role: str = "student",
    department: Optional[str] = None,
) -> Record:
    data = {
        "id": _next_user_id(db.client),
        "username": username,
        "email": email,
        "hashed_password": hashed_password,
        "role": role,
        "department": department,
        "created_at": _now(),
    }
    db.client.collection(USERS).document(_user_doc_id(username)).create(data)
    return Record(data)


def get_user_by_username(db: FirestoreSession, username: str) -> Optional[Record]:
    snapshot = db.client.collection(USERS).document(_user_doc_id(username)).get()
    return Record(snapshot.to_dict()) if snapshot.exists else None


def _first_user_where(db: FirestoreSession, field: str, value: Any) -> Optional[Record]:
    from google.cloud.firestore_v1.base_query import FieldFilter

    query = db.client.collection(USERS).where(filter=FieldFilter(field, "==", value)).limit(1)
    for snapshot in query.stream():
        return Record(snapshot.to_dict())
    return None


def get_user_by_email(db: FirestoreSession, email: str) -> Optional[Record]:
    return _first_user_where(db, "email", email)


def get_user_by_id(db: FirestoreSession, user_id: int) -> Optional[Record]:
    return _first_user_where(db, "id", user_id)


# ---------------------------------------------------------------------------
# Grievances
# ---------------------------------------------------------------------------

def _status_event(previous: Optional[str], new: str, changed_by: str) -> dict:
    return {
        "previous_status": previous,
        "new_status": new,
        "changed_by": changed_by,
        "changed_at": _now(),
    }


def create_grievance(
    db: FirestoreSession,
    *,
    grievance_id: str,
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
) -> FirestoreGrievance:
    now = _now()
    grievance = FirestoreGrievance({
        "grievance_id": grievance_id,
        "user_id": user_id,
        "message_type": message_type,
        "description": description,
        "language": language,
        "section": section,
        "hostel_block": hostel_block,
        "course_code": course_code,
        "event_name": event_name,
        "contact_no": contact_no,
        "status": "submitted",
        "created_at": now,
        "updated_at": now,
        "ai_analysis": None,
        "human_decision": None,
        "status_history": [_status_event(None, "submitted", created_by)],
        "audit_logs": [],
    })
    db._grievances[grievance_id] = grievance
    db._new.add(grievance_id)
    if commit:
        db.commit()
    return grievance


def grievance_id_exists(db: FirestoreSession, grievance_id: str) -> bool:
    if grievance_id in db._grievances:
        return True
    return db.client.collection(GRIEVANCES).document(grievance_id).get().exists


def get_grievance_by_id(db: FirestoreSession, grievance_id: str) -> Optional[FirestoreGrievance]:
    if grievance_id in db._grievances:
        return db._grievances[grievance_id]
    snapshot = db.client.collection(GRIEVANCES).document(grievance_id).get()
    if not snapshot.exists:
        return None
    return db._remember(FirestoreGrievance(snapshot.to_dict()))


def _newest_first(grievances: list[FirestoreGrievance]) -> list[FirestoreGrievance]:
    return sorted(grievances, key=lambda item: item.created_at or datetime.min, reverse=True)


def get_grievances_by_user(db: FirestoreSession, user_id: int) -> list:
    from google.cloud.firestore_v1.base_query import FieldFilter

    query = db.client.collection(GRIEVANCES).where(filter=FieldFilter("user_id", "==", user_id))
    return _newest_first([
        db._remember(FirestoreGrievance(snapshot.to_dict())) for snapshot in query.stream()
    ])


def get_all_grievances(db: FirestoreSession, skip: int = 0, limit: int = 200) -> list:
    from google.cloud import firestore

    query = (
        db.client.collection(GRIEVANCES)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .offset(skip)
        .limit(limit)
    )
    return [db._remember(FirestoreGrievance(snapshot.to_dict())) for snapshot in query.stream()]


def update_grievance_status(
    db: FirestoreSession,
    grievance_id: str,
    status: str,
    changed_by: str = "system",
    commit: bool = True,
) -> Optional[FirestoreGrievance]:
    grievance = get_grievance_by_id(db, grievance_id)
    if grievance and grievance.status != status:
        previous_status = grievance.status
        db._set(grievance, "status", status)
        db._set(grievance, "updated_at", _now())
        db._append(grievance, "status_history", _status_event(previous_status, status, changed_by))
        if commit:
            db.commit()
    return grievance


def save_ai_analysis(
    db: FirestoreSession, grievance_id: str, analysis: dict, commit: bool = True
) -> Record:
    grievance = get_grievance_by_id(db, grievance_id)
    if grievance is None:
        raise ValueError(f"Grievance {grievance_id} does not exist.")
    data = {
        "grievance_id": grievance_id,
        "predicted_master": _plain(analysis.get("predicted_master")),
        "predicted_category": _plain(analysis.get("predicted_category")),
        "predicted_subcategory": _plain(analysis.get("predicted_subcategory")),
        "confidence": _plain(analysis.get("confidence")),
        "sensitivity_flag": bool(analysis.get("sensitivity_flag", False)),
        "sensitivity_type": _plain(analysis.get("sensitivity_type", "NONE")),
        "sensitivity_evidence": json.dumps(_plain(analysis.get("sensitivity_evidence", []))),
        "priority_label": _plain(analysis.get("priority_label", "P3")),
        "routed_to": _plain(analysis.get("routed_to")),
        "needs_human_review": bool(analysis.get("needs_human_review", False)),
        "review_reasons": json.dumps(_plain(analysis.get("review_reasons", []))),
        "incident_id": _plain(analysis.get("incident_id")),
        "baseline_prediction": _plain(analysis.get("baseline_prediction")),
        "model_prediction": _plain(analysis.get("model_prediction")),
        "model_wins": _plain(analysis.get("model_wins")),
        "analysis_details": json.dumps(_plain(analysis), ensure_ascii=False),
        "created_at": _now(),
    }
    db._set(grievance, "ai_analysis", data)
    if commit:
        db.commit()
    return Record(data)


def save_human_decision(
    db: FirestoreSession, grievance_id: str, decision: dict, commit: bool = True
) -> Record:
    grievance = get_grievance_by_id(db, grievance_id)
    if grievance is None:
        raise ValueError(f"Grievance {grievance_id} does not exist.")
    if grievance.status in {"resolved", "closed"}:
        from src.db.crud import FinalizedDecisionError

        raise FinalizedDecisionError(
            "A decision cannot be changed after a grievance is resolved or closed."
        )
    data = {
        "grievance_id": grievance_id,
        "decided_by": decision.get("decided_by", "system"),
        "final_category": decision.get("final_category"),
        "final_subcategory": decision.get("final_subcategory"),
        "final_route": decision.get("final_route"),
        "final_priority": decision.get("final_priority"),
        "decision_notes": decision.get("decision_notes"),
        "resolution_solution": decision.get("resolution_solution"),
        "decided_at": _now(),
    }
    db._set(grievance, "human_decision", data)
    if commit:
        db.commit()
    return Record(data)


def create_audit_log(
    db: FirestoreSession,
    grievance_id: Optional[str],
    action: str,
    actor: str,
    details: Optional[dict] = None,
    commit: bool = True,
) -> Record:
    entry = {
        "grievance_id": grievance_id,
        "action": action,
        "actor": actor,
        "details": json.dumps(_plain(details or {})),
        "timestamp": _now(),
    }
    grievance = get_grievance_by_id(db, grievance_id) if grievance_id else None
    if grievance is not None:
        db._append(grievance, "audit_logs", entry)
    else:
        db._loose_audit.append(entry)
    if commit:
        db.commit()
    return Record(entry)


def get_pending_review_grievances(db: FirestoreSession) -> list:
    from google.cloud.firestore_v1.base_query import FieldFilter

    priority_order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    query = db.client.collection(GRIEVANCES).where(filter=FieldFilter("status", "==", "submitted"))
    grievances = [
        db._remember(FirestoreGrievance(snapshot.to_dict()))
        for snapshot in query.stream()
    ]
    pending = [g for g in grievances if g.ai_analysis and g.ai_analysis.needs_human_review]
    return sorted(
        pending,
        key=lambda g: priority_order.get(g.ai_analysis.priority_label or "P4", 3),
    )
