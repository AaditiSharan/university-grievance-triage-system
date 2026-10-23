"""
Incident matcher for UniResolve AI.

Checks whether an incoming grievance matches a known open incident so that
a pre-written reply template can be surfaced instead of creating duplicate
manual reviews.
"""
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent.parent

INCIDENTS_CSV = BASE_DIR / "data" / "synthetic" / "incidents.csv"

_incidents_cache: Optional[list] = None


def _load_incidents() -> list:
    """Lazily load incidents CSV."""
    global _incidents_cache
    if _incidents_cache is None:
        if not INCIDENTS_CSV.exists():
            _incidents_cache = []
            return _incidents_cache
        import csv
        with INCIDENTS_CSV.open(encoding="utf-8-sig", newline="") as incidents_file:
            _incidents_cache = list(csv.DictReader(incidents_file))
    return _incidents_cache


def match_incident(
    section: Optional[str],
    course_code: Optional[str],
    hostel_block: Optional[str],
    event_name: Optional[str],
    predicted_subcategory: Optional[str],
    description: Optional[str] = None,
) -> dict:
    """
    Try to match the grievance against open incidents.

    Matches only active incidents whose identifying key appears in the
    structured context or description. A shared subcategory is not sufficient
    to link unrelated courses, sections, hostels or events.

    Returns
    -------
    dict with keys:
        incident_found : bool
        incident_id    : str | None
        incident_title : str | None
        reply_template : str | None
        incident_status: str | None
    """
    incidents = _load_incidents()
    import re

    description_lower = (description or "").lower()

    def _contains_key(value: Optional[str], key: str) -> bool:
        if not value:
            return False
        value_lower = " ".join(value.lower().split())
        key_normalized = " ".join(key.split())
        return bool(
            re.search(
                r"(?<![\w])" + re.escape(key_normalized) + r"(?![\w])",
                value_lower,
            )
        )

    def _match(inc: dict) -> bool:
        mkt = str(inc.get("match_key_type", "")).lower()
        mkv = str(inc.get("match_key_value", "")).lower()
        subcategory = str(inc.get("subcategory", "")).lower()

        if str(inc.get("status", "")).lower() not in ("open", "active", "ongoing"):
            return False
        if not predicted_subcategory or subcategory != predicted_subcategory.lower():
            return False

        if mkt == "event":
            return _contains_key(event_name, mkv) or _contains_key(description_lower, mkv)
        if mkt == "section":
            return _contains_key(section, mkv) or _contains_key(description_lower, mkv)
        if mkt == "course":
            return _contains_key(course_code, mkv) or _contains_key(description_lower, mkv)
        if mkt in ("hostel", "block"):
            return _contains_key(hostel_block, mkv) or _contains_key(description_lower, mkv)
        if mkt == "paydate":
            return _contains_key(description_lower, mkv)
        return False

    for inc in incidents:
        if _match(inc):
            return {
                "incident_found": True,
                "incident_id": str(inc.get("incident_id", "")),
                "incident_title": str(inc.get("title", "")),
                "reply_template": str(inc.get("reply_template", "")),
                "incident_status": str(inc.get("status", "")),
            }

    return {
        "incident_found": False,
        "incident_id": None,
        "incident_title": None,
        "reply_template": None,
        "incident_status": None,
    }
