"""
api/ai_engine/PREDICTION_ENGINES/anomaly_detector.py
====================================================
Anomaly Detector — real-time prediction-level anomaly।
Prediction request pattern এ অস্বাভাবিকতা detect করো।
"""
import logging, math
from typing import List, Dict
logger = logging.getLogger(__name__)

class AnomalyDetector:
    """Real-time anomaly detection for prediction requests।"""

    def detect(self, input_data: dict, prediction_result: dict,
               context: dict = None) -> dict:
        context = context or {}
        score   = 0.0
        flags   = []

        # Prediction confidence check
        confidence = float(prediction_result.get('confidence', 1.0))
        if confidence < 0.20:
            score += 0.40; flags.append('very_low_confidence')
        elif confidence < 0.40:
            score += 0.20; flags.append('low_confidence')

        # Input feature range check
        numeric_vals = [v for v in input_data.values() if isinstance(v, (int, float))]
        if numeric_vals:
            if max(abs(v) for v in numeric_vals) > 1e6:
                score += 0.30; flags.append('extreme_input_values')

        # Request velocity
        rpm = float(context.get('requests_per_minute', 0))
        if rpm > 500:
            score += 0.50; flags.append('abnormal_request_velocity')
        elif rpm > 200:
            score += 0.25; flags.append('high_request_velocity')

        # Prediction value anomaly
        pred_val = float(prediction_result.get('predicted_value', 0.5))
        if pred_val >= 0.98 or pred_val <= 0.02:
            score += 0.20; flags.append('extreme_prediction_value')

        score = min(1.0, score)
        return {
            'is_anomaly':    score >= 0.60,
            'anomaly_score': round(score, 4),
            'severity':      'critical' if score >= 0.85 else 'high' if score >= 0.65 else 'medium' if score >= 0.45 else 'low',
            'flags':         flags,
            'confidence':    confidence,
        }

    def detect_batch_anomaly(self, batch_results: List[Dict]) -> dict:
        """Batch prediction results এ pattern anomaly detect।"""
        if not batch_results:
            return {'anomaly': False}
        scores  = [r.get('predicted_value', 0.5) for r in batch_results]
        mean    = sum(scores) / len(scores)
        std     = math.sqrt(sum((s - mean)**2 for s in scores) / max(len(scores)-1, 1))
        all_same = std < 0.001
        all_high = mean > 0.90
        all_low  = mean < 0.10
        return {
            'anomaly':     all_same or all_high or all_low,
            'mean_score':  round(mean, 4),
            'std_score':   round(std, 4),
            'flags':       (['all_identical'] if all_same else []) +
                           (['all_high_predictions'] if all_high else []) +
                           (['all_low_predictions'] if all_low else []),
            'batch_size':  len(batch_results),
        }

    def statistical_control(self, series: List[float],
                             window: int = 20) -> dict:
        """Statistical process control — UCL/LCL check।"""
        if len(series) < window:
            return {'in_control': True, 'reason': 'insufficient_data'}
        recent = series[-window:]
        mean   = sum(recent) / len(recent)
        std    = math.sqrt(sum((x - mean)**2 for x in recent) / max(len(recent)-1, 1))
        ucl    = mean + 3 * std
        lcl    = mean - 3 * std
        last   = series[-1]
        return {
            'in_control': lcl <= last <= ucl,
            'last_value': round(last, 4),
            'mean':       round(mean, 4),
            'ucl':        round(ucl, 4),
            'lcl':        round(lcl, 4),
            'sigma_dist': round(abs(last - mean) / max(std, 0.001), 2),
        }
