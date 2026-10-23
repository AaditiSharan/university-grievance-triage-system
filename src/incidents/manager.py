"""
Incident manager for UniResolve AI.

Provides read access to the incidents dataset.
"""
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent.parent
INCIDENTS_CSV = BASE_DIR / "data" / "synthetic" / "incidents.csv"

_cache: Optional[list] = None


def _load() -> list:
    global _cache
    if _cache is None:
        import pandas as pd
        if not INCIDENTS_CSV.exists():
            _cache = []
        else:
            df = pd.read_csv(INCIDENTS_CSV)
            _cache = df.to_dict(orient="records")
    return _cache


def get_all_incidents() -> list[dict]:
    """Return all incidents."""
    return _load()


def get_open_incidents() -> list[dict]:
    """Return incidents with status != 'resolved'."""
    return [inc for inc in _load() if str(inc.get("status", "")).lower() != "resolved"]


def get_incident_by_id(incident_id: str) -> Optional[dict]:
    """Return a single incident by ID, or None if not found."""
    for inc in _load():
        if str(inc.get("incident_id", "")).lower() == incident_id.lower():
            return inc
    return None
