"""
API flows against the Firestore backend.

Runs only when a Firestore emulator is available, for example:
  firebase emulators:start --only firestore --project demo-test
  FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 python -m pytest tests/test_firestore_backend.py
"""
import os
from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin, auth, rms, staff
from src.auth.security import get_password_hash
from src.db import crud
from src.db.connection import get_db
from src.db.firestore_store import FirestoreSession

EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST")
PROJECT = "demo-test"

pytestmark = pytest.mark.skipif(
    not EMULATOR_HOST, reason="FIRESTORE_EMULATOR_HOST is not set"
)


@pytest.fixture
def firestore_api() -> Iterator[tuple[TestClient, object]]:
    from google.cloud import firestore

    httpx.delete(
        f"http://{EMULATOR_HOST}/emulator/v1/projects/{PROJECT}/databases/(default)/documents"
    ).raise_for_status()
    client = firestore.Client(project=PROJECT)

    def override_db() -> Iterator[FirestoreSession]:
        db = FirestoreSession(client)
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api")
    app.include_router(rms.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(staff.router, prefix="/api")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client, client


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post("/api/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _register_student(client: TestClient, username: str, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": "test-password-123"},
    )
    assert response.status_code == 201, response.text
    return _login(client, username, "test-password-123")


def _provision(fs_client, username: str, role: str, department: str | None = None) -> None:
    crud.create_user(
        FirestoreSession(fs_client),
        username=username,
        email=f"{username}@example.edu",
        hashed_password=get_password_hash("staff-password-123"),
        role=role,
        department=department,
    )


def test_registration_rules_and_duplicates(firestore_api) -> None:
    client, _ = firestore_api
    _register_student(client, "student-one", "student@example.edu")

    duplicate_name = client.post(
        "/api/auth/register",
        json={"username": "student-one", "email": "other@example.edu", "password": "test-password-123"},
    )
    assert duplicate_name.status_code == 409
    duplicate_email = client.post(
        "/api/auth/register",
        json={"username": "student-two", "email": "student@example.edu", "password": "test-password-123"},
    )
    assert duplicate_email.status_code == 409

    staff = client.post(
        "/api/auth/register",
        json={
            "username": "exam-staff",
            "email": "exam@university.edu",
            "password": "test-password-123",
            "role": "staff",
            "department": "Examination Cell",
        },
    )
    assert staff.status_code == 201, staff.text
    assert staff.json()["department"] == "Examination Cell"
    me = client.get("/api/auth/me", headers=_login(client, "exam-staff", "test-password-123"))
    assert me.json()["role"] == "staff"
    assert me.json()["id"] != client.get(
        "/api/auth/me", headers=_login(client, "student-one", "test-password-123")
    ).json()["id"]


def test_submission_tracking_admin_review_and_finality(firestore_api) -> None:
    client, fs_client = firestore_api
    student = _register_student(client, "student-one", "student@example.edu")

    submission = client.post(
        "/api/rms/submit",
        headers=student,
        json={
            "description": (
                "The Wi-Fi connection in hostel BH-3 is repeatedly unavailable "
                "across devices today, disrupting coursework."
            ),
            "hostel_block": "BH-3",
            "urgent_deadline": True,
        },
    )
    assert submission.status_code == 201, submission.text
    grievance_id = submission.json()["grievance_id"]
    assert submission.json()["ai_analysis"]["incident_id"] == "INC-08"

    tracked = client.get(f"/api/rms/track/{grievance_id}", headers=student).json()
    assert tracked["status"] == "submitted"
    assert tracked["ai_analysis"]["priority_label"] == "P2"
    assert tracked["human_decision"] is None
    assert client.get("/api/rms/my-grievances", headers=student).json()[0]["grievance_id"] == grievance_id

    other = _register_student(client, "student-two", "second@example.edu")
    assert client.get(f"/api/rms/track/{grievance_id}", headers=other).status_code == 403

    _provision(fs_client, "review-admin", "admin")
    admin_headers = _login(client, "review-admin", "staff-password-123")
    listed = client.get("/api/rms/admin/grievances", headers=admin_headers)
    assert listed.status_code == 200
    assert [item["grievance_id"] for item in listed.json()] == [grievance_id]

    review = client.post(
        f"/api/rms/admin/review/{grievance_id}",
        headers=admin_headers,
        json={
            "final_category": "IT Services",
            "final_subcategory": "Wi-Fi Not Working",
            "final_route": "Network Operations",
            "final_priority": "P2",
            "decision_notes": "Confirmed the outage.",
            "new_status": "resolved",
        },
    )
    assert review.status_code == 200, review.text
    body = review.json()
    assert body["status"] == "resolved"
    assert body["human_decision"]["decided_by"] == "review-admin"
    assert [event["new_status"] for event in body["status_history"]] == ["submitted", "resolved"]
    assert body["audit_events"]

    stored = client.get(f"/api/rms/track/{grievance_id}", headers=student).json()
    assert stored["status"] == "resolved"
    assert "decided_by" not in stored["human_decision"]

    again = client.post(
        f"/api/rms/admin/review/{grievance_id}",
        headers=admin_headers,
        json={"decision_notes": "Trying to change it.", "new_status": "closed"},
    )
    assert again.status_code in {400, 409}

    stats = client.get("/api/rms/admin/stats", headers=admin_headers).json()
    assert stats["total"] == 1
    assert stats["pending_review"] == 0


def test_staff_queue_is_department_scoped(firestore_api) -> None:
    client, fs_client = firestore_api
    student = _register_student(client, "student-one", "student@example.edu")
    submitted = client.post(
        "/api/rms/submit",
        headers=student,
        json={"description": "The campus Wi-Fi connection repeatedly disconnects in the library every evening."},
    )
    assert submitted.status_code == 201, submitted.text
    grievance_id = submitted.json()["grievance_id"]
    department = submitted.json()["ai_analysis"]["routed_to"]

    _provision(fs_client, "dept-staff", "staff", department)
    _provision(fs_client, "other-staff", "staff", "Hostel Administration" if department != "Hostel Administration" else "IT Services")
    own = client.get("/api/rms/staff/grievances", headers=_login(client, "dept-staff", "staff-password-123"))
    assert own.status_code == 200, own.text
    assert grievance_id in [item["grievance_id"] for item in own.json()]
    foreign = client.get("/api/rms/staff/grievances", headers=_login(client, "other-staff", "staff-password-123"))
    assert grievance_id not in [item["grievance_id"] for item in foreign.json()]
    assert client.get("/api/rms/staff/grievances", headers=student).status_code == 403
