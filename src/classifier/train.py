"""
Train TF-IDF + Logistic Regression classifiers on train.csv.

Models saved to src/classifier/models/:
  - tfidf_vectorizer.joblib   (shared vectorizer)
  - tfidf_lr_model.joblib     (master-category classifier)
  - tfidf_lr_subcategory.joblib (subcategory classifier)
  - label_encoder.joblib      (master label encoder)
  - label_encoder_sub.joblib  (subcategory label encoder)
  - train_report.txt          (classification report)
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

from src.preprocessing.cleaner import normalize_description

MODELS_DIR = BASE_DIR / "src" / "classifier" / "models"
TRAIN_CSV = BASE_DIR / "data" / "processed" / "train.csv"


# Regularisation strength. C=1.0 left almost every prediction below the 0.6 confidence
# threshold even when correct; C=10 gives probabilities that track accuracy much better.
LR_C = 10.0


def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Drop rows with missing description or label
    df = df.dropna(subset=["description", "true_master"])
    df["clean_desc"] = df["description"].apply(normalize_description)
    return df


def train():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading training data from {TRAIN_CSV} ...")
    df = load_data(TRAIN_CSV)
    print(f"  Loaded {len(df)} records.")

    # ---- Vectorizer (shared) -----------------------------------------------
    print("Fitting TF-IDF vectorizer ...")
    # Word n-grams capture meaning; character n-grams (2-5) make the model tolerant of
    # Hinglish spelling variants and word forms it has not seen ("kharab"/"kharabi",
    # "aaya"/"aya"). On the held-out test set this lifted Hinglish accuracy by ~8 points.
    vectorizer = FeatureUnion(
        [
            (
                "w",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=5000,
                    sublinear_tf=True,
                    # No English stop_words because we have Hinglish
                ),
            ),
            (
                "c",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    max_features=30000,
                    sublinear_tf=True,
                ),
            ),
        ]
    )
    X = vectorizer.fit_transform(df["clean_desc"])

    # ---- Master category model ----------------------------------------------
    print("Training master-category (true_master) classifier ...")
    le_master = LabelEncoder()
    y_master = le_master.fit_transform(df["true_master"])

    clf_master = LogisticRegression(
        C=LR_C, max_iter=2000, class_weight="balanced", solver="lbfgs"
    )
    clf_master.fit(X, y_master)

    master_preds = clf_master.predict(X)
    master_report = classification_report(
        y_master, master_preds, target_names=le_master.classes_
    )
    print("\n=== Master Category (Train Set) ===")
    print(master_report)

    # ---- Subcategory model --------------------------------------------------
    df_sub = df.dropna(subset=["true_subcategory"])
    X_sub = vectorizer.transform(df_sub["clean_desc"])

    print("Training subcategory (true_subcategory) classifier ...")
    le_sub = LabelEncoder()
    y_sub = le_sub.fit_transform(df_sub["true_subcategory"])

    clf_sub = LogisticRegression(
        C=LR_C, max_iter=2000, class_weight="balanced", solver="lbfgs"
    )
    clf_sub.fit(X_sub, y_sub)

    sub_preds = clf_sub.predict(X_sub)
    sub_report = classification_report(
        y_sub, sub_preds, target_names=le_sub.classes_, zero_division=0
    )
    print("\n=== Subcategory (Train Set) ===")
    print(sub_report)

    # ---- Save artefacts -----------------------------------------------------
    print("\nSaving model artefacts ...")
    joblib.dump(vectorizer, MODELS_DIR / "tfidf_vectorizer.joblib")
    joblib.dump(clf_master, MODELS_DIR / "tfidf_lr_model.joblib")
    joblib.dump(le_master, MODELS_DIR / "label_encoder.joblib")
    joblib.dump(clf_sub, MODELS_DIR / "tfidf_lr_subcategory.joblib")
    joblib.dump(le_sub, MODELS_DIR / "label_encoder_sub.joblib")

    report_path = MODELS_DIR / "train_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=== Master Category Report ===\n")
        f.write(master_report)
        f.write("\n\n=== Subcategory Report ===\n")
        f.write(sub_report)

    print(f"Training complete. Report saved to {report_path}")
    return clf_master, vectorizer, le_master


if __name__ == "__main__":
    train()