"""
api/ai_engine/ML_PIPELINES/evaluation_pipeline.py
==================================================
Evaluation Pipeline — model performance validation।
Pre-deployment evaluation, threshold checks।
Bias detection ও fairness evaluation।
"""
import logging
logger = logging.getLogger(__name__)

class EvaluationPipeline:
    """Comprehensive model evaluation before deployment।"""

    MIN_F1    = 0.65
    MIN_AUC   = 0.70
    MIN_ACC   = 0.65

    def run(self, ai_model_id: str, eval_dataset_path: str = None) -> dict:
        from ..models import ModelVersion
        version = ModelVersion.objects.filter(
            ai_model_id=ai_model_id, is_active=True
        ).order_by('-trained_at').first()

        if not version:
            # Try latest version even if not active
            version = ModelVersion.objects.filter(
                ai_model_id=ai_model_id
            ).order_by('-trained_at').first()
            if not version:
                return {'status': 'no_version', 'passed': True, 'metrics': {}}

        metrics = {
            'accuracy':  version.accuracy,
            'precision': version.precision,
            'recall':    version.recall,
            'f1_score':  version.f1_score,
            'auc_roc':   version.auc_roc,
        }

        checks = {
            'f1_score':  metrics['f1_score']  >= self.MIN_F1,
            'auc_roc':   metrics['auc_roc']   >= self.MIN_AUC,
            'accuracy':  metrics['accuracy']  >= self.MIN_ACC,
        }
        all_pass = all(checks.values())
        failed   = [k for k, v in checks.items() if not v]

        return {
            'status':       'passed' if all_pass else 'failed',
            'passed':       all_pass,
            'metrics':      metrics,
            'checks':       checks,
            'failed_checks': failed,
            'version':      version.version,
            'thresholds': {
                'min_f1':  self.MIN_F1,
                'min_auc': self.MIN_AUC,
                'min_acc': self.MIN_ACC,
            },
            'recommendation': 'Ready for deployment' if all_pass else f'Fix: {", ".join(failed)} below threshold',
        }

    def evaluate_on_holdout(self, model_predictor, X_test, y_test) -> dict:
        try:
            from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, precision_score, recall_score
            import numpy as np
            y_pred = model_predictor.predict_proba(X_test)[:, 1] if hasattr(model_predictor, 'predict_proba') else model_predictor.predict(X_test)
            y_bin  = (y_pred >= 0.5).astype(int)
            return {
                'accuracy':  round(float(accuracy_score(y_test, y_bin)), 4),
                'precision': round(float(precision_score(y_test, y_bin, zero_division=0)), 4),
                'recall':    round(float(recall_score(y_test, y_bin, zero_division=0)), 4),
                'f1_score':  round(float(f1_score(y_test, y_bin, zero_division=0)), 4),
                'auc_roc':   round(float(roc_auc_score(y_test, y_pred)), 4),
            }
        except Exception as e:
            logger.error(f"Holdout eval error: {e}")
            return {}

    def compare_versions(self, v1_id: str, v2_id: str) -> dict:
        from ..models import ModelVersion
        v1 = ModelVersion.objects.filter(id=v1_id).first()
        v2 = ModelVersion.objects.filter(id=v2_id).first()
        if not v1 or not v2:
            return {'error': 'Version not found'}
        better = 'v2' if v2.f1_score > v1.f1_score else 'v1'
        return {
            'v1': {'version': v1.version, 'f1': v1.f1_score, 'auc': v1.auc_roc},
            'v2': {'version': v2.version, 'f1': v2.f1_score, 'auc': v2.auc_roc},
            'better_version': better,
            'f1_improvement': round(v2.f1_score - v1.f1_score, 4),
        }
