"""
SQLAlchemy ORM models for the UniResolve AI grievance triage system.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """System user – student, faculty, staff, or admin."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    # role: student | faculty | staff | admin
    role = Column(String(20), nullable=False, default="student")
    created_at = Column(DateTime, default=datetime.utcnow)

    grievances = relationship("Grievance", back_populates="user")


class Grievance(Base):
    """A submitted grievance record."""
    __tablename__ = "grievances"

    id = Column(Integer, primary_key=True, index=True)
    # Human-readable public ID  – GRV-YYYYMMDD-NNNNN
    grievance_id = Column(String(30), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    message_type = Column(String(30), nullable=False, default="Grievance")
    description = Column(Text, nullable=False)
    language = Column(String(20), default="english")
    section = Column(String(20), nullable=True)
    hostel_block = Column(String(20), nullable=True)
    course_code = Column(String(20), nullable=True)
    event_name = Column(String(100), nullable=True)
    contact_no = Column(String(20), nullable=True)

    # Lifecycle status: submitted | under_review | resolved | closed | escalated
    status = Column(String(30), default="submitted")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="grievances")
    ai_analysis = relationship(
        "AIAnalysis", back_populates="grievance", uselist=False
    )
    human_decision = relationship(
        "HumanDecision", back_populates="grievance", uselist=False
    )
    audit_logs = relationship("AuditLog", back_populates="grievance")


class AIAnalysis(Base):
    """AI triage result – kept separate from human decision."""
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, index=True)
    grievance_id = Column(
        String(30), ForeignKey("grievances.grievance_id"), unique=True, nullable=False
    )

    # ML classifier outputs
    predicted_master = Column(String(80), nullable=True)
    predicted_category = Column(String(80), nullable=True)
    predicted_subcategory = Column(String(120), nullable=True)
    confidence = Column(Float, nullable=True)

    # Sensitivity
    sensitivity_flag = Column(Boolean, default=False)
    sensitivity_type = Column(String(40), default="NONE")
    sensitivity_evidence = Column(Text, nullable=True)  # JSON list stored as text

    # Priority & routing
    priority_label = Column(String(5), default="P3")
    routed_to = Column(String(120), nullable=True)
    needs_human_review = Column(Boolean, default=False)
    review_reasons = Column(Text, nullable=True)  # JSON list stored as text

    # Incident linkage
    incident_id = Column(String(30), nullable=True)

    # Baseline vs ML comparison
    baseline_prediction = Column(String(80), nullable=True)
    model_prediction = Column(String(80), nullable=True)
    model_wins = Column(Boolean, nullable=True)
    analysis_details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    grievance = relationship("Grievance", back_populates="ai_analysis")


class HumanDecision(Base):
    """Override / final decision submitted by a human reviewer."""
    __tablename__ = "human_decisions"

    id = Column(Integer, primary_key=True, index=True)
    grievance_id = Column(
        String(30), ForeignKey("grievances.grievance_id"), unique=True, nullable=False
    )

    decided_by = Column(String(50), nullable=False)
    final_category = Column(String(80), nullable=True)
    final_subcategory = Column(String(120), nullable=True)
    final_route = Column(String(120), nullable=True)
    final_priority = Column(String(5), nullable=True)
    decision_notes = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.utcnow)

    grievance = relationship("Grievance", back_populates="human_decision")


class AuditLog(Base):
    """Immutable audit trail for every significant action."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    grievance_id = Column(
        String(30), ForeignKey("grievances.grievance_id"), nullable=True
    )
    action = Column(String(60), nullable=False)
    actor = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)   # JSON stored as text
    timestamp = Column(DateTime, default=datetime.utcnow)

    grievance = relationship("Grievance", back_populates="audit_logs")
