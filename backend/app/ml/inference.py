"""Load the saved classifiers and score ticket text."""

import json

import numpy as np

from backend.app.config import MODELS_DIR
from backend.app.ml.estimators import LabelledXGB, TextModel


def _score_lookup(scores, label: str):
    for row in scores:
        if row["label"] == label:
            return row["score"]
    return None


def _pack_scores(classes, proba, limit: int | None = None):
    labels = [str(label) for label in classes]
    packed = []
    for row in np.asarray(proba):
        pairs = [
            {"label": label, "score": round(float(score), 4)}
            for label, score in zip(labels, row)
        ]
        pairs.sort(key=lambda item: item["score"], reverse=True)
        packed.append(pairs[:limit] if limit else pairs)
    return packed


def _department_terms(model: TextModel, texts, labels, k: int = 6):
    classifier = model.classifier
    if not hasattr(classifier, "coef_"):
        return [[] for _ in texts]
    matrix = model.vectorizer.transform(texts).tocsr()
    names = model.vectorizer.get_feature_names_out()
    class_index = {str(label): index for index, label in enumerate(classifier.classes_)}
    coefficients = classifier.coef_
    explanations = []
    for row_index, label in enumerate(labels):
        start, end = matrix.indptr[row_index], matrix.indptr[row_index + 1]
        indexes = matrix.indices[start:end]
        weights = np.asarray(matrix.data[start:end]) * coefficients[class_index[str(label)], indexes]
        if weights.size == 0:
            explanations.append([])
            continue
        order = np.argsort(weights)[-k:][::-1]
        terms = []
        for position in order:
            if weights[position] <= 0:
                continue
            terms.append(
                {
                    "term": str(names[indexes[position]]),
                    "weight": round(float(weights[position]), 4),
                }
            )
        explanations.append(terms)
    return explanations


class Intelligence:
    def __init__(self):
        self.ready = False
        self.department: TextModel | None = None
        self.priority: TextModel | None = None
        self.sentiment: TextModel | None = None

    def load(self) -> bool:
        import joblib

        department_path = MODELS_DIR / "department.joblib"
        if not department_path.exists():
            self.ready = False
            return False
        # Importing the estimator classes above lets joblib restore them.
        assert TextModel and LabelledXGB
        self.department = joblib.load(department_path)
        self.priority = joblib.load(MODELS_DIR / "priority.joblib")
        self.sentiment = joblib.load(MODELS_DIR / "sentiment.joblib")
        self.ready = True
        return True

    def predict_many(self, texts: list[str]) -> list[dict]:
        if not self.ready:
            raise RuntimeError("Models are not loaded. Run python -m backend.scripts.bootstrap.")
        department_labels, department_proba = self.department.predict_and_proba(texts)
        priority_labels, priority_proba = self.priority.predict_and_proba(texts)
        sentiment_labels, sentiment_proba = self.sentiment.predict_and_proba(texts)
        department_labels = [str(label) for label in department_labels]
        priority_labels = [str(label) for label in priority_labels]
        sentiment_labels = [str(label) for label in sentiment_labels]
        department_scores = _pack_scores(self.department.classifier.classes_, department_proba, limit=4)
        priority_scores = _pack_scores(self.priority.classifier.classes_, priority_proba)
        sentiment_scores = _pack_scores(self.sentiment.classifier.classes_, sentiment_proba)
        terms = _department_terms(self.department, texts, department_labels)
        predictions = []
        for index in range(len(texts)):
            scores = {
                "department": department_scores[index],
                "priority": priority_scores[index],
                "sentiment": sentiment_scores[index],
                "terms": terms[index],
            }
            predictions.append(
                {
                    "department": department_labels[index],
                    "priority": priority_labels[index],
                    "sentiment": sentiment_labels[index],
                    "department_confidence": _score_lookup(scores["department"], department_labels[index]),
                    "priority_confidence": _score_lookup(scores["priority"], priority_labels[index]),
                    "sentiment_confidence": _score_lookup(scores["sentiment"], sentiment_labels[index]),
                    "scores": scores,
                }
            )
        return predictions

    def dumps(self, prediction: dict) -> str:
        return json.dumps(prediction["scores"])


intelligence = Intelligence()
