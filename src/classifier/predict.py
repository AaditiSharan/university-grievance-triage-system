"""
ML prediction module for UniResolve AI.

Loads trained TF-IDF + Logistic Regression models and returns a structured
prediction dict for a given input text.
"""
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent.parent

_vectorizer = None
_clf_master = None
_le_master = None
_clf_sub = None
_le_sub = None
_settings = None


def _evidence_word(feature_name: str):
    """Evidence shown to reviewers is words only: skip character n-grams, strip the union prefix."""
    name = str(feature_name)
    if name.startswith("c__"):
        return None
    return name[3:] if name.startswith("w__") else name


def _load_settings() -> dict:
    global _settings
    if _settings is None:
        import yaml
        with open(BASE_DIR / "config" / "settings.yaml", "r", encoding="utf-8") as f:
            _settings = yaml.safe_load(f)
    return _settings


def _load_models():
    """Lazy-load all model artefacts."""
    global _vectorizer, _clf_master, _le_master, _clf_sub, _le_sub

    if _clf_master is not None:
        return  # already loaded

    import joblib

    settings = _load_settings()
    models_dir = BASE_DIR / "src" / "classifier" / "models"

    _vectorizer = joblib.load(models_dir / "tfidf_vectorizer.joblib")
    _clf_master = joblib.load(models_dir / "tfidf_lr_model.joblib")
    _le_master = joblib.load(models_dir / "label_encoder.joblib")

    sub_path = models_dir / "tfidf_lr_subcategory.joblib"
    sub_le_path = models_dir / "label_encoder_sub.joblib"
    if sub_path.exists() and sub_le_path.exists():
        _clf_sub = joblib.load(sub_path)
        _le_sub = joblib.load(sub_le_path)


def models_available() -> bool:
    """Return True if trained model files exist on disk."""
    models_dir = BASE_DIR / "src" / "classifier" / "models"
    return (
        (models_dir / "tfidf_vectorizer.joblib").exists()
        and (models_dir / "tfidf_lr_model.joblib").exists()
        and (models_dir / "label_encoder.joblib").exists()
    )


def predict(text: str) -> dict:
    """
    Predict grievance category for *text*.

    Returns
    -------
    dict with keys:
        predicted_master    : str
        predicted_subcategory: str
        confidence          : float
        top_classes         : list[dict]  (top 3 master predictions)
        low_confidence      : bool
        needs_human_review  : bool
        model_available     : bool
    """
    from src.preprocessing.cleaner import normalize_description

    settings = _load_settings()
    conf_threshold: float = settings["classifier"]["confidence_threshold"]
    low_conf_threshold: float = settings["classifier"]["low_confidence_threshold"]

    if not models_available():
        return {
            "predicted_master": "Unknown",
            "predicted_subcategory": "Unknown",
            "confidence": 0.0,
            "top_classes": [],
            "low_confidence": True,
            "needs_human_review": True,
            "model_available": False,
            "explanation": ["TF-IDF/Logistic Regression artifacts are not trained yet."],
        }

    _load_models()

    cleaned = normalize_description(text)
    X = _vectorizer.transform([cleaned])

    # Master category
    proba = _clf_master.predict_proba(X)[0]
    top_indices = proba.argsort()[::-1][:3]
    top_classes = [
        {
            "label": str(_le_master.classes_[i]),
            "category": str(_le_master.classes_[i]),
            "probability": round(float(proba[i]), 4),
        }
        for i in top_indices
    ]

    predicted_master = top_classes[0]["category"]
    confidence = top_classes[0]["probability"]

    # Subcategory
    predicted_subcategory = "UNCLEAR"
    if _clf_sub is not None and _le_sub is not None:
        sub_proba = _clf_sub.predict_proba(X)[0]
        sub_idx = sub_proba.argmax()
        predicted_subcategory = str(_le_sub.classes_[sub_idx])

    low_confidence = confidence < conf_threshold
    needs_human_review = confidence < low_conf_threshold

    feature_names = _vectorizer.get_feature_names_out()
    coefficients = _clf_master.coef_
    class_index = int(top_indices[0])
    row = X.tocsr()
    active_features = [
        (float(row[0, feature_index] * coefficients[class_index, feature_index]), feature_index)
        for feature_index in row.indices
    ]
    evidence: list[str] = []
    for weight, index in sorted(active_features, reverse=True):
        if weight <= 0 or len(evidence) == 5:
            break
        word = _evidence_word(feature_names[index])
        if word is not None:
            evidence.append(word)

    return {
        "predicted_master": predicted_master,
        "predicted_subcategory": predicted_subcategory,
        "confidence": round(confidence, 4),
        "top_classes": top_classes,
        "low_confidence": low_confidence,
        "needs_human_review": needs_human_review,
        "model_available": True,
        "explanation": evidence,
    }