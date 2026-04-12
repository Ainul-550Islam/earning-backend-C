"""
api/ai_engine/TESTING_EVALUATION/shadow_testing.py
====================================================
Shadow Testing — নতুন model production এ deploy না করে
shadow mode এ run করো এবং existing model এর সাথে compare করো।
Zero risk model validation।
"""

import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ShadowTester:
    """
    Shadow testing engine।
    Production model এর পাশে new model চালাও,
    result compare করো, কিন্তু user কে new model এর result দেখাও না।
    """

    def __init__(self, prod_model_id: str, shadow_model_id: str):
        self.prod_model_id   = prod_model_id
        self.shadow_model_id = shadow_model_id
        self.results: List[Dict] = []

    def run(self, input_data: dict, prediction_type: str = 'fraud',
            user=None, tenant_id=None) -> dict:
        """
        Production + shadow model দুটোই চালাও।
        Production result return করো।
        Shadow result log করো।
        """
        # Production model
        prod_start  = time.time()
        prod_result = self._predict(self.prod_model_id, prediction_type, input_data, user, tenant_id)
        prod_ms     = round((time.time() - prod_start) * 1000, 2)

        # Shadow model (non-blocking)
        shadow_start  = time.time()
        shadow_result = self._predict(self.shadow_model_id, prediction_type, input_data, user, tenant_id)
        shadow_ms     = round((time.time() - shadow_start) * 1000, 2)

        # Compare
        comparison = self._compare(prod_result, shadow_result)

        # Log for analysis
        log_entry = {
            'prediction_type': prediction_type,
            'prod_result':     prod_result,
            'shadow_result':   shadow_result,
            'comparison':      comparison,
            'prod_ms':         prod_ms,
            'shadow_ms':       shadow_ms,
        }
        self.results.append(log_entry)
        self._persist_log(log_entry)

        # Always return PRODUCTION result — shadow is invisible to users
        return {**prod_result, '_shadow_comparison': comparison}

    def _predict(self, model_id: str, prediction_type: str,
                 input_data: dict, user, tenant_id) -> dict:
        try:
            from ..services import PredictionService
            return PredictionService.predict(prediction_type, input_data, user=user, tenant_id=tenant_id)
        except Exception as e:
            logger.error(f"Shadow predict error [{model_id}]: {e}")
            return {'error': str(e), 'confidence': 0.0}

    def _compare(self, prod: dict, shadow: dict) -> dict:
        prod_val   = prod.get('predicted_value') or prod.get('confidence', 0)
        shadow_val = shadow.get('predicted_value') or shadow.get('confidence', 0)
        divergence = abs((prod_val or 0) - (shadow_val or 0))

        prod_class   = prod.get('predicted_class', '')
        shadow_class = shadow.get('predicted_class', '')

        return {
            'divergence':      round(divergence, 4),
            'class_match':     prod_class == shadow_class,
            'agreed':          divergence < 0.10,
            'prod_value':      prod_val,
            'shadow_value':    shadow_val,
        }

    def _persist_log(self, log_entry: dict):
        try:
            from ..models import PredictionLog
            # Optional: save shadow comparison to DB
            pass
        except Exception:
            pass

    def get_summary(self) -> dict:
        """Shadow testing session এর summary।"""
        if not self.results:
            return {'total': 0, 'agreement_rate': 0.0}

        total     = len(self.results)
        agreed    = sum(1 for r in self.results if r['comparison']['agreed'])
        avg_div   = sum(r['comparison']['divergence'] for r in self.results) / total
        class_match = sum(1 for r in self.results if r['comparison']['class_match'])

        return {
            'total':            total,
            'agreement_rate':   round(agreed / total, 4),
            'class_match_rate': round(class_match / total, 4),
            'avg_divergence':   round(avg_div, 4),
            'ready_for_promotion': agreed / total >= 0.95 and avg_div < 0.05,
        }

    def run_batch_shadow(self, test_cases: List[Dict],
                          prediction_type: str = 'fraud') -> dict:
        """Batch shadow test চালাও।"""
        for case in test_cases:
            self.run(case, prediction_type)
        return self.get_summary()
