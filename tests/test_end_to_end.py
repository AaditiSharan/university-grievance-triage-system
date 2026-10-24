from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.routers import admin, auth, rms, staff
from src.auth.security import get_password_hash
from src.db.connection import get_db
from src.db.models import Base, User


@pytest.fixture
def api() -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_db() -> Iterator:
        db = test_sessions()
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
    with TestClient(app) as client:
        yield client, test_sessions
    app.dependency_overrides.clear()
    engine.dispose()


def register_and_login(client: TestClient, username: str, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": "test-password-123"},
    )
    assert response.status_code == 201, response.text
    login_response = client.post(
        "/api/auth/login",
        data={"username": username, "password": "test-password-123"},
    )
    assert login_response.status_code == 200, login_response.text
    return login_response.json()["access_token"]


def test_grievance_submission_tracking_and_human_review(api: tuple[TestClient, sessionmaker]) -> None:
    client, sessions = api
    student_token = register_and_login(client, "student-one", "student@example.edu")
    student_headers = {"Authorization": f"Bearer {student_token}"}

    prohibited_admin = client.post(
        "/api/auth/register",
        json={
            "username": "unapproved-admin",
            "email": "unapproved@example.edu",
            "password": "test-password-123",
            "role": "admin",
        },
    )
    assert prohibited_admin.status_code == 403
    prohibited_staff = client.post(
        "/api/auth/register",
        json={
            "username": "self-appointed-staff",
            "email": "self-appointed-staff@example.edu",
            "password": "test-password-123",
            "role": "staff",
        },
    )
    assert prohibited_staff.status_code == 403

    submission = client.post(
        "/api/rms/submit",
        headers=student_headers,
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
    submitted = submission.json()
    grievance_id = submitted["grievance_id"]
    analysis = submitted["ai_analysis"]
    assert submitted["status"] == "submitted"
    assert "human review" in submitted["message"].lower()
    assert analysis["classifier_available"] is True
    assert analysis["predicted_master"] == "IT Services"
    assert analysis["incident_found"] is True
    assert analysis["incident_id"] == "INC-08"
    assert analysis["priority_label"] == "P2"

    tracked = client.get(f"/api/rms/track/{grievance_id}", headers=student_headers)
    assert tracked.status_code == 200
    assert tracked.json()["ai_analysis"]["incident_id"] == "INC-08"
    assert client.get("/api/rms/my-grievances", headers=student_headers).json()[0][
        "grievance_id"
    ] == grievance_id

    another_student = register_and_login(client, "student-two", "second@example.edu")
    denied_track = client.get(
        f"/api/rms/track/{grievance_id}",
        headers={"Authorization": f"Bearer {another_student}"},
    )
    assert denied_track.status_code == 403
    assert client.get("/api/rms/admin/grievances", headers=student_headers).status_code == 403

    with sessions() as db:
        db.add(
            User(
                username="review-admin",
                email="review-admin@example.edu",
                hashed_password=get_password_hash("admin-password-123"),
                role="admin",
            )
        )
        db.commit()
    admin_token = client.post(
        "/api/auth/login",
        data={"username": "review-admin", "password": "admin-password-123"},
    ).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    review = client.post(
        f"/api/rms/admin/review/{grievance_id}",
        headers=admin_headers,
        json={
            "final_category": "IT Services",
            "final_subcategory": "Wi-Fi Not Working",
            "final_route": "Network Operations",
            "final_priority": "P2",
            "decision_notes": "Verified with the student and confirmed the outage.",
            "new_status": "resolved",
        },
    )
    assert review.status_code == 200, review.text
    reviewed = review.json()
    assert reviewed["status"] == "resolved"
    assert reviewed["human_decision"]["decided_by"] == "review-admin"
    assert reviewed["human_decision"]["final_route"] == "Network Operations"
    assert reviewed["ai_analysis"]["routed_to"] == "IT Services"
    student_view_after_review = client.get(
        f"/api/rms/track/{grievance_id}", headers=student_headers
    ).json()
    assert "audit_events" not in student_view_after_review
    assert student_view_after_review["status_history"][-1]["changed_by"] == "review-admin"

    stats = client.get("/api/rms/admin/stats", headers=admin_headers).json()
    assert stats["total"] == 1
    assert stats["pending_review"] == 0


def test_incomplete_submission_is_accepted_but_requires_review(
    api: tuple[TestClient, sessionmaker],
) -> None:
    client, _ = api
    token = register_and_login(client, "short-user", "short@example.edu")
    response = client.post(
        "/api/rms/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": "Hi, thanks."},
    )
    assert response.status_code == 201, response.text
    analysis = response.json()["ai_analysis"]
    assert analysis["is_complete"] is False
    assert analysis["needs_human_review"] is True
    assert len(analysis["completeness_issues"]) >= 2

    empty_description = client.post(
        "/api/rms/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": ""},
    )
    assert empty_description.status_code == 422


def test_vague_follow_up_is_marked_incomplete() -> None:
    from src.pipeline import run_triage_pipeline

    result = run_triage_pipeline({"description": "Issue not solved yet asap"})
    assert result["is_complete"] is False
    assert result["needs_human_review"] is True
    assert result["priority_label"] == "P3"


def test_multi_issue_submission_is_queued_for_human_review() -> None:
    from src.pipeline import run_triage_pipeline

    result = run_triage_pipeline(
        {
            "description": (
                "My course registration has an error. Also, my friend needs a counsellor "
                "after hurting themselves."
            )
        }
    )
    assert result["needs_human_review"] is True
    assert any("multiple issue categories" in reason.lower() for reason in result["review_reasons"])


def test_threat_language_is_escalated_for_human_review() -> None:
    from src.pipeline import run_triage_pipeline

    result = run_triage_pipeline(
        {
            "description": (
                "I am being threatened by another student and do not feel safe "
                "on campus. Please contact me confidentially."
            )
        }
    )
    assert result["sensitivity_flag"] is True
    assert result["sensitivity_type"] == "SAFETY"
    assert result["priority_label"] == "P1"
    assert result["routed_to"] == "Security & Student Welfare"
    assert result["needs_human_review"] is True


@pytest.mark.parametrize(
    "description",
    [
        "Our club is organising an anti-ragging awareness drive. How do we register?",
        "There is no ragging in GH-3, but the Wi-Fi has been down for two days.",
        "I was admitted to the hospital last week and need an attendance update.",
    ],
)
def test_harmless_sensitive_keyword_context_is_not_escalated(description: str) -> None:
    from src.pipeline import run_triage_pipeline

    result = run_triage_pipeline({"description": description})
    assert result["sensitivity_flag"] is False


def test_deadline_is_priority_not_sensitivity() -> None:
    from src.pipeline import run_triage_pipeline

    result = run_triage_pipeline(
        {
            "description": (
                "The fee deadline is tomorrow due to a delayed loan payment."
            )
        }
    )
    assert result["sensitivity_flag"] is False
    assert result["priority_label"] == "P2"


def test_hinglish_medical_emergency_escalates() -> None:
    from src.pipeline import run_triage_pipeline

    result = run_triage_pipeline(
        {"description": "Mere dost ka accident ho gaya hai aur bahut chot lagi hai."}
    )
    assert result["sensitivity_flag"] is True
    assert result["priority_label"] == "P1"
    assert result["needs_human_review"] is True


def test_open_incident_requires_matching_subcategory_and_location() -> None:
    from src.incidents.matcher import match_incident

    wrong_location = match_incident(
        section=None,
        course_code=None,
        hostel_block="BH-2",
        event_name=None,
        predicted_subcategory="Wi-Fi Not Working",
        description="Wi-Fi is unavailable in hostel BH-2.",
    )
    wrong_subcategory = match_incident(
        section=None,
        course_code=None,
        hostel_block="BH-3",
        event_name=None,
        predicted_subcategory="Room Maintenance",
        description="There is a room maintenance problem in BH-3.",
    )
    assert wrong_location["incident_found"] is False
    assert wrong_subcategory["incident_found"] is False


def test_database_startup_adds_analysis_details_to_existing_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.db.connection as connection

    engine = create_engine("sqlite://")
    with engine.begin() as db_connection:
        db_connection.execute(text("CREATE TABLE ai_analyses (id INTEGER PRIMARY KEY)"))
        db_connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        db_connection.execute(text("CREATE TABLE human_decisions (id INTEGER PRIMARY KEY)"))
    monkeypatch.setattr(connection, "engine", engine)
    connection.create_tables()
    column_names = {
        column["name"] for column in inspect(engine).get_columns("ai_analyses")
    }
    assert "analysis_details" in column_names
    assert "department" in {
        column["name"] for column in inspect(engine).get_columns("users")
    }
    assert "resolution_solution" in {
        column["name"] for column in inspect(engine).get_columns("human_decisions")
    }
    assert inspect(engine).has_table("status_history")
    engine.dispose()


def _provision_account(
    client: TestClient,
    sessions: sessionmaker,
    username: str,
    role: str,
    department: str | None = None,
) -> str:
    with sessions() as db:
        db.add(
            User(
                username=username,
                email=f"{username}@example.edu",
                hashed_password=get_password_hash("staff-password-123"),
                role=role,
                department=department,
            )
        )
        db.commit()
    response = client.post(
        "/api/auth/login",
        data={"username": username, "password": "staff-password-123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _seed_grievance(
    sessions: sessionmaker,
    *,
    department: str = "IT Services",
    sensitive: bool = False,
) -> str:
    from src.db import crud

    with sessions() as db:
        grievance = crud.create_grievance(
            db,
            user_id=None,
            message_type="Grievance",
            description="The campus Wi-Fi connection repeatedly disconnects.",
            created_by="student",
        )
        crud.save_ai_analysis(
            db,
            grievance.grievance_id,
            {
                "predicted_master": department,
                "predicted_category": "Connectivity",
                "predicted_subcategory": "Wi-Fi Not Working",
                "sensitivity_flag": sensitive,
                "sensitivity_type": "SAFETY" if sensitive else "NONE",
                "priority_label": "P2",
                "routed_to": department,
                "needs_human_review": True,
            },
        )
        return grievance.grievance_id


def test_staff_queue_is_department_scoped_and_faculty_is_read_only(
    api: tuple[TestClient, sessionmaker],
) -> None:
    client, sessions = api
    local_id = _seed_grievance(sessions, department="IT Services")
    other_id = _seed_grievance(sessions, department="Housing")
    staff_token = _provision_account(client, sessions, "it-staff", "staff", "IT Services")
    faculty_token = _provision_account(client, sessions, "it-faculty", "faculty", "IT Services")
    student_token = register_and_login(client, "queue-student", "queue-student@example.edu")

    queue = client.get(
        "/api/rms/staff/grievances",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert queue.status_code == 200
    assert [item["grievance_id"] for item in queue.json()] == [local_id]
    assert other_id not in [item["grievance_id"] for item in queue.json()]
    denied_student = client.get(
        "/api/rms/staff/grievances",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert denied_student.status_code == 403
    denied_faculty_review = client.post(
        f"/api/rms/staff/review/{local_id}",
        headers={"Authorization": f"Bearer {faculty_token}"},
        json={"new_status": "under_review"},
    )
    assert denied_faculty_review.status_code == 403
    denied_cross_department = client.post(
        f"/api/rms/staff/review/{other_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"new_status": "under_review"},
    )
    assert denied_cross_department.status_code == 403


def test_sensitive_grievance_cannot_receive_ai_draft_but_human_review_can_resolve(
    api: tuple[TestClient, sessionmaker],
) -> None:
    client, sessions = api
    grievance_id = _seed_grievance(sessions, sensitive=True)
    from src.db.models import AIAnalysis

    with sessions() as db:
        analysis = db.query(AIAnalysis).filter_by(grievance_id=grievance_id).one()
        analysis.sensitivity_flag = False
        db.commit()
    token = _provision_account(client, sessions, "safety-staff", "staff", "IT Services")
    headers = {"Authorization": f"Bearer {token}"}

    denied = client.post(
        "/api/rms/staff/draft-resolutions",
        headers=headers,
        json={"grievance_ids": [grievance_id]},
    )
    assert denied.status_code == 403

    approved_human = client.post(
        f"/api/rms/staff/review/{grievance_id}",
        headers=headers,
        json={
            "new_status": "resolved",
            "resolution_solution": "A staff member contacted the submitter and arranged a safe follow-up.",
            "decision_notes": "Handled directly by the designated welfare team.",
        },
    )
    assert approved_human.status_code == 200
    body = approved_human.json()
    assert body["status"] == "resolved"
    assert body["human_decision"]["resolution_solution"].startswith("A staff member")
    assert body["status_history"][-1]["changed_by"] == "safety-staff"
    assert body["audit_events"][-1]["action"] == "HUMAN_REVIEW_APPROVED"


def test_ai_draft_requires_explicit_request_and_does_not_resolve(
    api: tuple[TestClient, sessionmaker],
) -> None:
    client, sessions = api
    grievance_id = _seed_grievance(sessions)
    token = _provision_account(client, sessions, "draft-staff", "staff", "IT Services")
    response = client.post(
        "/api/rms/staff/draft-resolutions",
        headers={"Authorization": f"Bearer {token}"},
        json={"grievance_ids": [grievance_id]},
    )
    assert response.status_code == 200
    assert response.json()["saved_or_sent"] is False
    assert response.json()["drafts"][0]["requires_individual_review"] is True
    staff_queue = client.get(
        "/api/rms/staff/grievances", headers={"Authorization": f"Bearer {token}"}
    ).json()
    audit_actions = [
        event["action"]
        for event in next(item for item in staff_queue if item["grievance_id"] == grievance_id)["audit_events"]
    ]
    assert "AI_RESOLUTION_DRAFT_REQUESTED" in audit_actions
    missing_solution = client.post(
        f"/api/rms/staff/review/{grievance_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_status": "resolved"},
    )
    assert missing_solution.status_code == 422
    from src.db import crud

    with sessions() as db:
        grievance = crud.get_grievance_by_id(db, grievance_id)
        assert grievance.status == "submitted"
        assert grievance.human_decision is None


def test_bulk_resolution_requires_individual_approval_and_tracks_status(
    api: tuple[TestClient, sessionmaker],
) -> None:
    client, sessions = api
    ids = [_seed_grievance(sessions), _seed_grievance(sessions)]
    token = _provision_account(client, sessions, "bulk-staff", "staff", "IT Services")
    headers = {"Authorization": f"Bearer {token}"}
    item = lambda grievance_id, approved: {
        "grievance_id": grievance_id,
        "new_status": "resolved",
        "resolution_solution": f"Staff solution for {grievance_id}",
        "approved": approved,
    }

    rejected = client.post(
        "/api/rms/staff/bulk-review",
        headers=headers,
        json={"items": [item(ids[0], True), item(ids[1], False)]},
    )
    assert rejected.status_code == 422
    result = client.post(
        "/api/rms/staff/bulk-review",
        headers=headers,
        json={"items": [item(ids[0], True), item(ids[1], True)]},
    )
    assert result.status_code == 200, result.text
    assert result.json()["count"] == 2
    for updated in result.json()["updated"]:
        assert updated["status"] == "resolved"
        assert updated["status_history"][-1]["changed_by"] == "bulk-staff"
        assert updated["human_decision"]["resolution_solution"].startswith("Staff solution")
