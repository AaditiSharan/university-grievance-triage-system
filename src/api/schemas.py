"""
Pydantic schemas for UniResolve AI API.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=72)
    role: str = "student"

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("username must contain at least 3 non-space characters")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or any(char.isspace() for char in normalized):
            raise ValueError("A valid email address is required")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 UTF-8 bytes")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"student", "faculty", "staff", "admin"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    department: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Grievances
# ---------------------------------------------------------------------------

class GrievanceSubmit(BaseModel):
    message_type: str = Field(default="Grievance", max_length=30)
    description: str = Field(min_length=1, max_length=10000)
    language: str = "english"
    section: Optional[str] = None
    hostel_block: Optional[str] = None
    course_code: Optional[str] = None
    event_name: Optional[str] = None
    contact_no: Optional[str] = None
    urgent_deadline: bool = False
    selected_master: Optional[str] = None
    selected_category: Optional[str] = None
    selected_subcategory: Optional[str] = None

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, value: str) -> str:
        allowed = {
            "Grievance", "Query", "Request", "Feedback", "Positive Feedback",
            "Assistance", "Enquiry",
        }
        if value not in allowed:
            raise ValueError(f"message_type must be one of {sorted(allowed)}")
        return value


class AIAnalysisResponse(BaseModel):
    predicted_master: Optional[str] = None
    predicted_category: Optional[str] = None
    predicted_subcategory: Optional[str] = None
    confidence: Optional[float] = None
    sensitivity_flag: bool = False
    sensitivity_type: str = "NONE"
    sensitivity_evidence: Optional[list] = None
    priority_label: str = "P3"
    routed_to: Optional[str] = None
    needs_human_review: bool = False
    review_reasons: Optional[list] = None
    incident_id: Optional[str] = None
    baseline_prediction: Optional[str] = None
    model_prediction: Optional[str] = None
    model_wins: Optional[bool] = None
    top_classes: list = Field(default_factory=list)
    low_confidence: bool = True
    classifier_explanation: list = Field(default_factory=list)
    classifier_available: bool = False
    baseline_keywords: list = Field(default_factory=list)
    baseline_categories: list = Field(default_factory=list)
    completeness_issues: list = Field(default_factory=list)
    is_complete: bool = False
    priority_score: int = 0
    priority_reasons: list = Field(default_factory=list)
    routing_basis: str = "default"
    incident_found: bool = False
    incident_title: Optional[str] = None
    reply_template: Optional[str] = None
    incident_status: Optional[str] = None

    model_config = {"from_attributes": True}


class GrievanceResponse(BaseModel):
    grievance_id: str
    message_type: str
    description: str
    language: str
    section: Optional[str] = None
    hostel_block: Optional[str] = None
    course_code: Optional[str] = None
    event_name: Optional[str] = None
    contact_no: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    ai_analysis: Optional[AIAnalysisResponse] = None

    model_config = {"from_attributes": True}


class GrievanceSubmitResponse(BaseModel):
    grievance_id: str
    status: str
    message: str
    ai_analysis: dict
    incident: Optional[dict] = None


# ---------------------------------------------------------------------------
# Human Decision
# ---------------------------------------------------------------------------

class HumanDecisionSubmit(BaseModel):
    final_category: Optional[str] = Field(default=None, max_length=80)
    final_subcategory: Optional[str] = Field(default=None, max_length=120)
    final_route: Optional[str] = Field(default=None, max_length=120)
    final_priority: Optional[str] = Field(default=None, pattern=r"^P[1-4]$")
    decision_notes: Optional[str] = Field(default=None, max_length=4000)
    resolution_solution: Optional[str] = Field(default=None, max_length=10000)
    new_status: str = "under_review"

    @field_validator("new_status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"under_review", "resolved", "closed", "escalated"}
        if value not in allowed:
            raise ValueError(f"new_status must be one of {sorted(allowed)}")
        return value


# ---------------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------------

class HumanDecisionResponse(BaseModel):
    decided_by: str
    final_category: Optional[str] = None
    final_subcategory: Optional[str] = None
    final_route: Optional[str] = None
    final_priority: Optional[str] = None
    decision_notes: Optional[str] = None
    resolution_solution: Optional[str] = None
    decided_at: datetime

    model_config = {"from_attributes": True}


class AdminGrievanceView(BaseModel):
    grievance_id: str
    message_type: str
    description: str
    status: str
    created_at: datetime
    ai_analysis: Optional[AIAnalysisResponse] = None
    human_decision: Optional[HumanDecisionResponse] = None

    model_config = {"from_attributes": True}


class StatsResponse(BaseModel):
    total: int
    by_status: dict
    by_priority: dict
    by_master_category: dict = Field(default_factory=dict)
    pending_review: int
    sensitive_count: int = 0


class DraftRequest(BaseModel):
    grievance_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("grievance_ids")
    @classmethod
    def require_unique_grievances(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Each grievance may be drafted only once per request.")
        return value


class BulkDecisionItem(HumanDecisionSubmit):
    grievance_id: str = Field(min_length=1, max_length=30)
    approved: bool


class BulkDecisionSubmit(BaseModel):
    items: list[BulkDecisionItem] = Field(min_length=1, max_length=50)

    @field_validator("items")
    @classmethod
    def require_unique_approved_items(cls, value: list[BulkDecisionItem]) -> list[BulkDecisionItem]:
        ids = [item.grievance_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Each grievance may appear only once in a bulk action.")
        if any(not item.approved for item in value):
            raise ValueError("Every case must be individually approved before saving.")
        return value


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class IncidentResponse(BaseModel):
    incident_id: str
    title: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    reply_template: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    expected_resolution_date: Optional[str] = None
    linked_request_count: Optional[int] = None

    model_config = {"from_attributes": True}
