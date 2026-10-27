"""
JWT authentication and password hashing utilities.
"""
import os
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import jwt
import yaml
from passlib.context import CryptContext

# A random process-local key is used for development; deployments should set SECRET_KEY.
SECRET_KEY: str = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

PROJECT_ROOT = Path(__file__).resolve().parents[2]
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _load_yaml_file(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def get_allowed_staff_email_domains() -> set[str]:
    """Return the configured institutional domains allowed for staff/faculty self-registration."""
    env_value = os.getenv("STAFF_EMAIL_DOMAINS") or os.getenv("ALLOWED_STAFF_EMAIL_DOMAINS")
    if env_value:
        raw_value = env_value
    else:
        settings = _load_yaml_file(PROJECT_ROOT / "config" / "settings.yaml")
        auth_settings = settings.get("auth", {}) if isinstance(settings.get("auth", {}), dict) else {}
        raw_value = auth_settings.get("staff_email_domains", ["example.edu", "university.edu"])
        if isinstance(raw_value, str):
            raw_value = [raw_value]
        raw_value = ",".join(str(item).strip() for item in raw_value if str(item).strip())
    domains = {
        item.strip().lower().lstrip(".")
        for item in str(raw_value).split(",")
        if item.strip()
    }
    return domains or {"example.edu", "university.edu"}


def get_valid_department_names() -> list[str]:
    """Return the department names that may be assigned to staff/faculty users."""
    routing = _load_yaml_file(PROJECT_ROOT / "config" / "routing_table.yaml")
    routes = routing.get("routes", {}) if isinstance(routing.get("routes", {}), dict) else {}
    departments = {
        str(value).strip()
        for value in routes.values()
        if str(value).strip()
    }
    return sorted(departments, key=lambda item: item.casefold())


def normalize_department_name(name: Optional[str]) -> Optional[str]:
    """Regularize a department string for comparison and storage."""
    if name is None:
        return None
    cleaned = str(name).strip()
    return cleaned or None


def is_valid_department_name(name: Optional[str]) -> bool:
    """Whether a department is one of the configured routing destinations."""
    cleaned = normalize_department_name(name)
    if not cleaned:
        return False
    valid_departments = {department.casefold(): department for department in get_valid_department_names()}
    return cleaned.casefold() in valid_departments


def infer_department_from_email(email: str) -> Optional[str]:
    """Return a valid department inferred from an institutional email address."""
    if not email or "@" not in email:
        return None
    local_part = email.split("@", 1)[0].strip().lower()
    tokens = set(re.sub(r"[^a-z0-9]+", " ", local_part).split())
    department_map = {
        "it": "IT Services",
        "tech": "IT Services",
        "network": "IT Services",
        "systems": "IT Services",
        "support": "IT Services",
        "exam": "Examination Cell",
        "examination": "Examination Cell",
        "results": "Examination Cell",
        "account": "Accounts Office",
        "accounts": "Accounts Office",
        "finance": "Accounts Office",
        "fee": "Accounts Office",
        "fees": "Accounts Office",
        "library": "Library",
        "hostel": "Hostel Administration",
        "residence": "Hostel Administration",
        "mess": "Hostel Administration",
        "transport": "Transport Office",
        "security": "Security & Student Welfare",
        "welfare": "Security & Student Welfare",
        "counselling": "Counselling Centre",
        "counseling": "Counselling Centre",
        "scholarship": "Scholarship Cell",
        "acad": "Academic Operations",
        "academic": "Academic Operations",
        "course": "Academic Operations",
    }
    for token in sorted(tokens, key=len, reverse=True):
        department = department_map.get(token)
        if department and is_valid_department_name(department):
            return department
    return None


def resolve_staff_department(email: str, requested_department: Optional[str] = None) -> Optional[str]:
    """Return a validated staff department from a secure request or email-derived inference."""
    if requested_department is not None:
        cleaned = normalize_department_name(requested_department)
        if cleaned is None:
            return None
        valid_departments = {department.casefold(): department for department in get_valid_department_names()}
        canonical = valid_departments.get(cleaned.casefold())
        if canonical is None:
            return None
        return canonical
    inferred = infer_department_from_email(email)
    if inferred is None:
        return None
    valid_departments = {department.casefold(): department for department in get_valid_department_names()}
    return valid_departments.get(inferred.casefold())


def is_allowed_staff_email(email: str) -> bool:
    """Whether the email matches the institutional staff/faculty verification policy."""
    if not email or "@" not in email:
        return False
    email_domain = email.rsplit("@", 1)[1].strip().lower()
    allowed_domains = get_allowed_staff_email_domains()
    if not allowed_domains:
        return False
    return any(
        email_domain == domain or email_domain.endswith(f".{domain}")
        for domain in allowed_domains
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return pwd_context.hash(password)


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token.  Returns None on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
