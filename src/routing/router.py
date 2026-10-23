"""
Grievance routing module for UniResolve AI.

Looks up the target department for a predicted subcategory using
config/routing_table.yaml, with a sensitivity override when applicable.
"""
from pathlib import Path
from typing import Optional

import yaml

BASE_DIR = Path(__file__).parent.parent.parent

_routing_cache: Optional[dict] = None


def _load_routing_table() -> dict:
    global _routing_cache
    if _routing_cache is None:
        p = BASE_DIR / "config" / "routing_table.yaml"
        with open(p, "r", encoding="utf-8") as f:
            _routing_cache = yaml.safe_load(f)
    return _routing_cache


def route_grievance(
    predicted_subcategory: str,
    sensitivity_result: dict,
) -> dict:
    """
    Determine the routing department for a grievance.

    Parameters
    ----------
    predicted_subcategory : str
        ML-predicted (or baseline) subcategory label.
    sensitivity_result : dict
        Output of check_sensitivity().

    Returns
    -------
    dict with keys:
        department    : str
        routing_basis : str   ("sensitivity_override" | "routing_table" | "default")
    """
    routing = _load_routing_table()
    routes: dict = routing.get("routes", {})
    default_dept: str = routing.get("default", "General Grievance Queue")
    unclear_dept: str = routing.get("unclear", "Manual Triage")

    # 1. Sensitivity route override has highest priority
    route_override: Optional[str] = sensitivity_result.get("route_override")
    if route_override:
        return {
            "department": route_override,
            "routing_basis": "sensitivity_override",
        }

    # 2. Lookup subcategory in routing table
    if predicted_subcategory and predicted_subcategory not in ("Unknown", "UNCLEAR"):
        dept = routes.get(predicted_subcategory)
        if dept:
            return {
                "department": dept,
                "routing_basis": "routing_table",
            }

    # 3. Fall back to default queue
    dept = unclear_dept if predicted_subcategory in ("Unknown", "UNCLEAR", None) else default_dept
    return {
        "department": dept,
        "routing_basis": "default",
    }
