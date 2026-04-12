"""Supervised Learning — fraud classification using labeled training data."""
import logging
logger = logging.getLogger(__name__)

class SupervisedFraudClassifier:
    """
    Trains and evaluates a supervised fraud classifier.
    Requires scikit-learn: pip install scikit-learn
    """
    def __init__(self, model_type: str = 'random_forest'):
        self.model_type = model_type
        self.model = None

    def train(self, X: list, y: list) -> dict:
        try:
            from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import classification_report, roc_auc_score
            import numpy as np

            clf = (RandomForestClassifier(n_estimators=100, random_state=42)
                   if self.model_type == 'random_forest'
                   else GradientBoostingClassifier(n_estimators=100, random_state=42))

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            clf.fit(X_train, y_train)
            self.model = clf

            y_prob = clf.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, y_prob)
            report = classification_report(y_test, clf.predict(X_test), output_dict=True)

            return {
                'auc_roc': round(auc, 4),
                'precision': round(report['1']['precision'], 4),
                'recall': round(report['1']['recall'], 4),
                'f1_score': round(report['1']['f1-score'], 4),
                'accuracy': round(report['accuracy'], 4),
                'training_samples': len(X_train),
                'test_samples': len(X_test),
            }
        except ImportError:
            return {'error': 'scikit-learn not installed. Run: pip install scikit-learn'}
        except Exception as e:
            return {'error': str(e)}

    def save(self, path: str):
        if self.model:
            import joblib
            joblib.dump(self.model, path)
            return path
        return None
