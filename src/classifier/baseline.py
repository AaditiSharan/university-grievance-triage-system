"""
Rule-based keyword classifier (no ML) for UniResolve AI.

Acts as a baseline and fallback when the ML model is unavailable or
when confidence is very low.
"""
import re

from src.preprocessing.cleaner import clean_text

KEYWORD_RULES: dict[str, list[str]] = {
    "Academics": [
        "attendance", "timetable", "class", "course", "online class",
        "elective", "lecture", "syllabus", "professor", "teacher",
        "tutorial", "lab", "practical",
    ],
    "Examination": [
        "result", "marks", "exam", "admit card", "datesheet",
        "re-evaluation", "revaluation", "grade", "scorecard",
        "supplementary", "backlog", "paper",
    ],
    "Finance": [
        "fee", "scholarship", "receipt", "payment", "concession",
        "refund", "challan", "dues", "money", "stipend",
    ],
    "Hostel": [
        "hostel", "room", "mess", "food", "maintenance", "warden",
        "bed", "bathroom", "washroom", "toilet", "water", "electricity",
        "laundry", "pg", "accommodation",
    ],
    "IT Services": [
        "wifi", "wi-fi", "internet", "ums", "login", "network",
        "portal", "website", "password", "access", "server", "vpn",
        "email", "id", "account",
    ],
    "Administration": [
        "id card", "bonafide", "bus", "transport", "library",
        "documents", "certificate", "noc", "migration", "registrar",
        "office", "administration", "book", "vehicle",
    ],
    "Events & Activities": [
        "event", "duty leave", " dl ", "certificate", "cultural",
        "techfest", "fest", "competition", "sports", "club",
        "society", "nss", "ncc", "hackathon",
    ],
    "Student Welfare": [
        "ragging", "harassment", "threat", "mental", "emergency",
        "safety", "violence", "bully", "assault", "suicide",
        "depression", "anxiety", "health", "medical", "sick",
    ],
    "Feedback & Suggestions": [
        "feedback", "suggestion", "appreciate", "thank you",
        "good", "excellent", "improve", "recommend", "great",
    ],
}


def baseline_predict(text: str) -> dict:
    """
    Apply keyword rules to *text* and return the best-matching category.

    Returns
    -------
    dict with keys:
        prediction       : str   (category name or "Unknown")
        matched_keywords : list[str]
    """
    cleaned = clean_text(text)

    scores: dict[str, list[str]] = {}
    for category, keywords in KEYWORD_RULES.items():
        matched = [
            kw for kw in keywords
            if re.search(r"\b" + re.escape(kw.strip().lower()) + r"\b", cleaned)
        ]
        if matched:
            scores[category] = matched

    if not scores:
        return {
            "prediction": "Unknown",
            "matched_keywords": [],
            "matched_categories": [],
            "matched_keywords_by_category": {},
        }

    # Pick the category with the most keyword hits
    best_cat = max(scores, key=lambda c: (len(scores[c]), c))
    return {
        "prediction": best_cat,
        "matched_keywords": scores[best_cat],
        "matched_categories": list(scores),
        "matched_keywords_by_category": scores,
    }
