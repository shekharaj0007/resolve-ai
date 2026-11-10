"""Train department, priority, and sentiment models and record holdout macro-F1."""

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.decomposition import TruncatedSVD

from backend.app.config import DATA_DIR, MODELS_DIR
from backend.app.domain import DEPARTMENTS, PRIORITIES, SENTIMENTS
from backend.app.ml.dataset import generate
from backend.app.ml.embeddings import SvdEmbedder
from backend.app.ml.estimators import LabelledXGB, TextModel
from backend.app.ml.text import ticket_text

TARGET_MACRO_F1 = 0.85
NOTE = (
    "Macro-F1 is computed on a stratified 20% holdout. The corpus is synthetic "
    "Fieldnote mail, and scenarios repeat across the split, so this checks that "
    "the pipelines separate the corpus. It is not a production benchmark. Target: 85% macro-F1."
)


def _vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        max_features=15000,
        sublinear_tf=True,
        dtype=np.float32,
    )


def _report(y_true, y_pred, labels) -> dict:
    truth = [str(value) for value in y_true]
    predicted = [str(value) for value in y_pred]
    report = classification_report(truth, predicted, labels=list(labels), output_dict=True, zero_division=0)
    return {
        "macro_f1": round(float(report["macro avg"]["f1-score"]), 4),
        "accuracy": round(float(report["accuracy"]), 4),
        "test_size": len(truth),
        "per_class": [
            {
                "label": label,
                "precision": round(float(report[label]["precision"]), 4),
                "recall": round(float(report[label]["recall"]), 4),
                "f1": round(float(report[label]["f1-score"]), 4),
                "support": int(report[label]["support"]),
            }
            for label in labels
        ],
    }


def _linear_terms(model: TextModel, k: int = 8) -> list[dict]:
    names = model.vectorizer.get_feature_names_out()
    rows = []
    for index, label in enumerate(model.classifier.classes_):
        coefficients = model.classifier.coef_[index]
        top = np.argsort(coefficients)[-k:][::-1]
        rows.append({"label": str(label), "terms": [str(names[position]) for position in top]})
    return rows


def _priority_features(model: TextModel, k: int = 12) -> list[dict]:
    names = model.vectorizer.get_feature_names_out()
    gain = model.classifier.model.get_booster().get_score(importance_type="gain")
    ranked = []
    for key, value in gain.items():
        if not str(key).startswith("f"):
            continue
        index = int(str(key)[1:])
        if index >= len(names):
            continue
        ranked.append((str(names[index]), float(value)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [{"term": term, "gain": round(score, 4)} for term, score in ranked[:k]]


def _fit_svd(texts) -> None:
    tfidf = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_features=12000,
    )
    svd = TruncatedSVD(n_components=128, random_state=42)
    svd.fit(tfidf.fit_transform(texts))
    SvdEmbedder(tfidf, svd).save(MODELS_DIR / "svd_embedder.joblib")


def train() -> dict:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(generate())
    frame["text"] = [ticket_text(subject, body) for subject, body in zip(frame["subject"], frame["body"])]
    print(f"Corpus: {len(frame)} tickets", flush=True)
    for column in ("department", "priority", "sentiment"):
        print(column, frame[column].value_counts().to_dict(), flush=True)

    indices = np.arange(len(frame))
    train_idx, test_idx = train_test_split(
        indices,
        test_size=0.2,
        random_state=42,
        stratify=frame["department"],
    )
    split = np.array(["train"] * len(frame), dtype=object)
    split[test_idx] = "holdout"
    frame["split"] = split

    def fit_and_score(model: TextModel, column: str, labels) -> dict:
        model.fit(frame.loc[train_idx, "text"].tolist(), frame.loc[train_idx, column].tolist())
        predicted = model.predict(frame.loc[test_idx, "text"].tolist())
        report = _report(frame.loc[test_idx, column].tolist(), predicted, labels)
        report["train_size"] = int(len(train_idx))
        return report

    department_model = TextModel(
        _vectorizer(),
        LogisticRegression(max_iter=400, C=3.0, class_weight="balanced", solver="saga", tol=1e-3, random_state=42),
    )
    priority_model = TextModel(_vectorizer(), LabelledXGB())
    sentiment_model = TextModel(
        _vectorizer(),
        LogisticRegression(max_iter=400, C=3.0, class_weight="balanced", solver="saga", tol=1e-3, random_state=42),
    )

    print("Training department classifier...", flush=True)
    department = fit_and_score(department_model, "department", [item["slug"] for item in DEPARTMENTS])
    department["algorithm"] = "TF-IDF + Logistic Regression"
    department["terms"] = _linear_terms(department_model)

    print("Training priority model...", flush=True)
    priority = fit_and_score(priority_model, "priority", list(PRIORITIES))
    priority["algorithm"] = "TF-IDF + XGBoost"
    try:
        priority["top_features"] = _priority_features(priority_model)
    except Exception as exc:
        print(f"Skipping priority feature gains: {exc}", flush=True)

    print("Training sentiment classifier...", flush=True)
    sentiment = fit_and_score(sentiment_model, "sentiment", list(SENTIMENTS))
    sentiment["algorithm"] = "TF-IDF + Logistic Regression"
    sentiment["terms"] = _linear_terms(sentiment_model)

    print("Fitting SVD embedder...", flush=True)
    _fit_svd(frame["text"].tolist())

    joblib.dump(department_model, MODELS_DIR / "department.joblib", compress=3)
    joblib.dump(priority_model, MODELS_DIR / "priority.joblib", compress=3)
    joblib.dump(sentiment_model, MODELS_DIR / "sentiment.joblib", compress=3)

    export = frame.drop(columns=["text"])
    export.to_csv(DATA_DIR / "tickets.csv", index=False)

    metrics = {
        "ready": True,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "target_macro_f1": TARGET_MACRO_F1,
        "dataset": {
            "name": "Fieldnote support corpus",
            "rows": int(len(frame)),
            "holdout_rows": int(len(test_idx)),
            "holdout_fraction": 0.2,
            "note": NOTE,
        },
        "department": department,
        "priority": priority,
        "sentiment": sentiment,
        "embedder": None,
    }
    (MODELS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    for name, block in ("department", department), ("priority", priority), ("sentiment", sentiment):
        print(f"{name} macro-F1 {block['macro_f1']:.4f} accuracy {block['accuracy']:.4f}", flush=True)
        if block["macro_f1"] < TARGET_MACRO_F1:
            raise SystemExit(f"{name} macro-F1 {block['macro_f1']:.3f} is below {TARGET_MACRO_F1:.2f}")
    return metrics


if __name__ == "__main__":
    train()
