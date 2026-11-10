"""Estimators saved with the trained pipelines.

Joblib restores these classes by their module path, so keep the names stable.
"""

import numpy as np
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


class LabelledXGB:
    """XGBoost classifier that accepts the string labels used everywhere else."""

    def __init__(self):
        self.encoder = LabelEncoder()
        self.model = XGBClassifier(
            n_estimators=160,
            max_depth=4,
            learning_rate=0.15,
            subsample=0.9,
            colsample_bytree=0.7,
            min_child_weight=2,
            reg_lambda=1.0,
            objective="multi:softprob",
            tree_method="hist",
            random_state=42,
            n_jobs=4,
            verbosity=0,
        )

    def fit(self, features, labels):
        encoded = self.encoder.fit_transform(labels)
        self.model.fit(features, encoded)
        return self

    def predict(self, features):
        predicted = np.asarray(self.model.predict(features)).astype(int).ravel()
        return self.encoder.inverse_transform(predicted)

    def predict_proba(self, features):
        return self.model.predict_proba(features)

    @property
    def classes_(self):
        return self.encoder.classes_


class TextModel:
    def __init__(self, vectorizer, classifier):
        self.vectorizer = vectorizer
        self.classifier = classifier

    def fit(self, texts, labels):
        features = self.vectorizer.fit_transform(texts)
        self.classifier.fit(features, labels)
        return self

    def predict(self, texts):
        return self.classifier.predict(self.vectorizer.transform(texts))

    def predict_proba(self, texts):
        return self.classifier.predict_proba(self.vectorizer.transform(texts))

    def predict_and_proba(self, texts):
        features = self.vectorizer.transform(texts)
        return self.classifier.predict(features), self.classifier.predict_proba(features)
