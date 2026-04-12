"""
api/ai_engine/ML_PIPELINES/drift_detection_pipeline.py
=======================================================
Data Drift Detection Pipeline।
Production model এর data distribution পরিবর্তন detect করো।
Automatic retraining trigger ও alert generation।
"""

import logging
import math
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DriftDetectionPipeline:
    """
    Production data drift detection।
    PSI, KS-test, chi-squared test দিয়ে drift measure করো।
    """

    PSI_NO_DRIFT    = 0.10
    PSI_MINOR_DRIFT = 0.20
    KS_THRESHOLD    = 0.10

    def __init__(self, ai_model):
        self.ai_model = ai_model

    def run(self, reference_data: dict = None,
            current_data: dict = None) -> dict:
        """
        Full drift detection pipeline।
        reference_data: training-time distributions
        current_data: current production distributions
        """
        from django.utils import timezone

        logger.info(f"Drift detection for: {self.ai_model.name}")

        # Use stored distributions if not provided
        if reference_data is None:
            reference_data = self._load_reference_distributions()
        if current_data is None:
            current_data = self._load_current_distributions()

        # Run drift tests
        psi_results = self._compute_psi_all(reference_data, current_data)
        ks_results  = self._compute_ks_all(reference_data, current_data)

        # Overall drift score
        drift_score = self._compute_overall_drift(psi_results, ks_results)
        psi_score   = max((r['psi'] for r in psi_results.values()), default=0.0)
        ks_stat     = max((r['ks_statistic'] for r in ks_results.values()), default=0.0)

        status = self._classify_drift(drift_score, psi_score)
        retrain = status == 'critical'

        drifted_features = [
            f for f, r in psi_results.items()
            if r['psi'] >= self.PSI_MINOR_DRIFT
        ]

        # Save drift log
        log = self._save_drift_log(drift_score, psi_score, ks_stat, status,
                                    drifted_features, retrain)

        # Trigger retraining if needed
        if retrain:
            self._trigger_retrain()

        return {
            'ai_model':            self.ai_model.name,
            'status':              status,
            'drift_score':         round(drift_score, 6),
            'psi_score':           round(psi_score, 6),
            'ks_statistic':        round(ks_stat, 6),
            'drifted_features':    drifted_features,
            'feature_psi':         {f: round(r['psi'], 6) for f, r in psi_results.items()},
            'feature_ks':          {f: round(r['ks_statistic'], 6) for f, r in ks_results.items()},
            'retrain_recommended': retrain,
            'detected_at':         str(timezone.now()),
        }

    def _compute_psi(self, reference: List[float],
                      current: List[float],
                      buckets: int = 10) -> float:
        """Population Stability Index (PSI) compute করো।"""
        eps = 1e-8
        if not reference or not current:
            return 0.0

        all_vals = reference + current
        min_v    = min(all_vals)
        max_v    = max(all_vals)
        if min_v == max_v:
            return 0.0

        bucket_size = (max_v - min_v) / buckets
        psi = 0.0

        for i in range(buckets):
            low  = min_v + i * bucket_size
            high = low + bucket_size
            ref_pct = len([x for x in reference if low <= x < high]) / max(len(reference), 1) + eps
            cur_pct = len([x for x in current   if low <= x < high]) / max(len(current),   1) + eps
            psi += (cur_pct - ref_pct) * math.log(cur_pct / ref_pct)

        return round(abs(psi), 6)

    def _compute_ks(self, reference: List[float],
                     current: List[float]) -> float:
        """Kolmogorov-Smirnov test statistic।"""
        if not reference or not current:
            return 0.0
        try:
            from scipy.stats import ks_2samp
            stat, _ = ks_2samp(reference, current)
            return round(float(stat), 6)
        except ImportError:
            # Manual KS calculation
            ref_sorted = sorted(reference)
            cur_sorted = sorted(current)
            n_ref = len(ref_sorted)
            n_cur = len(cur_sorted)

            all_vals = sorted(set(ref_sorted + cur_sorted))
            max_diff = 0.0
            for val in all_vals:
                cdf_ref = sum(1 for x in ref_sorted if x <= val) / n_ref
                cdf_cur = sum(1 for x in cur_sorted if x <= val) / n_cur
                max_diff = max(max_diff, abs(cdf_ref - cdf_cur))
            return round(max_diff, 6)

    def _compute_psi_all(self, reference: dict, current: dict) -> Dict[str, Dict]:
        results = {}
        for feature in reference:
            if feature in current:
                psi = self._compute_psi(reference[feature], current[feature])
                status = (
                    'critical' if psi >= self.PSI_MINOR_DRIFT else
                    'warning'  if psi >= self.PSI_NO_DRIFT else
                    'stable'
                )
                results[feature] = {'psi': psi, 'status': status}
        return results

    def _compute_ks_all(self, reference: dict, current: dict) -> Dict[str, Dict]:
        results = {}
        for feature in reference:
            if feature in current:
                ks = self._compute_ks(reference[feature], current[feature])
                results[feature] = {
                    'ks_statistic': ks,
                    'drifted':      ks >= self.KS_THRESHOLD,
                }
        return results

    def _compute_overall_drift(self, psi_results: dict, ks_results: dict) -> float:
        if not psi_results:
            return 0.0
        psi_vals = [r['psi'] for r in psi_results.values()]
        ks_vals  = [r['ks_statistic'] for r in ks_results.values()]
        avg_psi  = sum(psi_vals) / len(psi_vals)
        avg_ks   = sum(ks_vals)  / len(ks_vals) if ks_vals else 0
        return min(1.0, (avg_psi + avg_ks) / 2)

    def _classify_drift(self, drift_score: float, psi_score: float) -> str:
        if drift_score >= 0.30 or psi_score >= self.PSI_MINOR_DRIFT:
            return 'critical'
        if drift_score >= 0.15 or psi_score >= self.PSI_NO_DRIFT:
            return 'warning'
        return 'normal'

    def _load_reference_distributions(self) -> dict:
        """Reference distribution load করো (training time)।"""
        # Production এ: training dataset এর feature distributions store করো
        # এবং এখানে load করো
        return {}

    def _load_current_distributions(self) -> dict:
        """Current production distributions collect করো।"""
        try:
            from ..models import PredictionLog
            from django.utils import timezone
            from datetime import timedelta
            import ast

            since = timezone.now() - timedelta(days=7)
            logs  = PredictionLog.objects.filter(
                ai_model=self.ai_model,
                created_at__gte=since,
            ).values_list('input_data', flat=True)[:1000]

            distributions: Dict[str, List[float]] = {}
            for log in logs:
                if isinstance(log, dict):
                    for k, v in log.items():
                        if isinstance(v, (int, float)):
                            distributions.setdefault(k, []).append(float(v))

            return distributions
        except Exception as e:
            logger.error(f"Load current dist error: {e}")
            return {}

    def _save_drift_log(self, drift_score, psi_score, ks_stat,
                         status, drifted_features, retrain) -> object:
        try:
            from ..models import DataDriftLog
            from django.utils import timezone

            log = DataDriftLog.objects.create(
                ai_model=self.ai_model,
                drift_type='feature',
                status=status,
                drift_score=drift_score,
                psi_score=psi_score,
                ks_statistic=ks_stat,
                threshold=self.PSI_NO_DRIFT,
                drifted_features=drifted_features,
                retrain_recommended=retrain,
                detected_at=timezone.now(),
            )
            return log
        except Exception as e:
            logger.error(f"Drift log save error: {e}")
            return None

    def _trigger_retrain(self):
        """Critical drift detected — retrain trigger করো।"""
        try:
            from ..tasks import task_train_model
            task_train_model.apply_async(
                args=[str(self.ai_model.id), 'auto'],
                queue='ai_tasks',
            )
            logger.warning(f"Retrain triggered for: {self.ai_model.name}")
        except Exception as e:
            logger.error(f"Retrain trigger error: {e}")

    def monitor_feature_drift(self, feature_name: str,
                               reference_vals: List[float],
                               current_vals: List[float]) -> dict:
        """Single feature এর drift monitor করো।"""
        psi = self._compute_psi(reference_vals, current_vals)
        ks  = self._compute_ks(reference_vals, current_vals)

        return {
            'feature':         feature_name,
            'psi':             round(psi, 6),
            'ks_statistic':    round(ks, 6),
            'status':          self._classify_drift(psi, psi),
            'drifted':         psi >= self.PSI_NO_DRIFT,
            'recommendation':  'Investigate feature engineering' if psi >= self.PSI_MINOR_DRIFT else 'Monitor',
        }

    def generate_drift_report(self) -> dict:
        """Comprehensive drift analysis report।"""
        from ..models import DataDriftLog
        recent_logs = DataDriftLog.objects.filter(
            ai_model=self.ai_model
        ).order_by('-detected_at')[:30]

        if not recent_logs:
            return {'status': 'no_drift_history', 'model': self.ai_model.name}

        statuses   = [log.status for log in recent_logs]
        drift_trend = 'improving' if statuses[:5].count('normal') > statuses[-5:].count('normal') \
                      else 'worsening' if statuses[:5].count('critical') < statuses[-5:].count('critical') \
                      else 'stable'

        return {
            'model':          self.ai_model.name,
            'latest_status':  statuses[0] if statuses else 'unknown',
            'drift_trend':    drift_trend,
            'critical_count': statuses.count('critical'),
            'warning_count':  statuses.count('warning'),
            'normal_count':   statuses.count('normal'),
            'retrain_count':  sum(1 for log in recent_logs if log.retrain_recommended),
            'period':         '30 latest detections',
        }
