"""
api/ai_engine/NLP_ENGINES/text_classifier.py
=============================================
Text Classifier — multi-class ও multi-label text classification।
Support ticket routing, review categorization, intent classification।
Bengali + English language support।
Marketing platform এর customer support automation।
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Keyword taxonomy ────────────────────────────────────────────────────────
LABEL_KEYWORDS: Dict[str, List[str]] = {
    'payment':       ['payment', 'withdraw', 'payout', 'money', 'cash', 'bank',
                      'bkash', 'nagad', 'rocket', 'পেমেন্ট', 'টাকা', 'উত্তোলন'],
    'account':       ['account', 'login', 'password', 'register', 'verify', 'kyc',
                      'blocked', 'banned', 'অ্যাকাউন্ট', 'লগইন', 'পাসওয়ার্ড'],
    'offer':         ['offer', 'task', 'reward', 'complete', 'earn', 'coin',
                      'অফার', 'রিওয়ার্ড', 'উপার্জন', 'টাস্ক'],
    'referral':      ['refer', 'invite', 'friend', 'referral', 'code', 'bonus',
                      'রেফার', 'বন্ধু', 'কোড', 'বোনাস'],
    'technical':     ['error', 'bug', 'crash', 'not working', 'slow', 'app',
                      'ত্রুটি', 'কাজ করছে না', 'স্লো'],
    'complaint':     ['problem', 'issue', 'wrong', 'bad', 'cheat', 'fraud',
                      'সমস্যা', 'অভিযোগ', 'প্রতারণা', 'ভুল'],
    'appreciation':  ['thanks', 'great', 'excellent', 'love', 'awesome', 'best',
                      'ধন্যবাদ', 'চমৎকার', 'ভালো', 'অসাধারণ'],
    'inquiry':       ['how', 'what', 'when', 'where', 'why', 'can i', 'help',
                      'কিভাবে', 'কখন', 'কোথায়', 'জানতে চাই'],
    'spam':          ['buy now', 'click here', 'free money', 'win', 'prize',
                      'limited time', 'act now', 'guaranteed'],
    'fraud_report':  ['scam', 'stolen', 'hack', 'unauthorized', 'fake', 'stolen account',
                      'প্রতারণা', 'হ্যাক', 'চুরি'],
}

# Priority order for support routing
PRIORITY_MAP = {
    'fraud_report': 'critical',
    'complaint':    'high',
    'payment':      'high',
    'account':      'medium',
    'technical':    'medium',
    'offer':        'low',
    'referral':     'low',
    'inquiry':      'low',
    'appreciation': 'low',
    'spam':         'low',
}


class TextClassifier:
    """
    Multi-label text classifier।
    Customer support automation, review categorization,
    spam filtering, intent routing।
    """

    def __init__(self, use_ml_model: bool = False, model_path: str = None):
        self.use_ml_model = use_ml_model
        self.model_path   = model_path
        self._ml_model    = None

    def classify(self, text: str, labels: List[str] = None,
                  top_k: int = 3) -> Dict:
        """
        Text classify করো।
        Returns top-k predicted labels with confidence scores।
        """
        if not text or not text.strip():
            return self._empty_result()

        labels = labels or list(LABEL_KEYWORDS.keys())

        # ML model available হলে use করো
        if self.use_ml_model and self._ml_model:
            return self._ml_classify(text, labels, top_k)

        # Rule-based classification
        return self._rule_classify(text, labels, top_k)

    def _rule_classify(self, text: str, labels: List[str], top_k: int) -> Dict:
        """Keyword-based rule classification।"""
        text_lower = text.lower()
        scores     = {}

        for label in labels:
            keywords = LABEL_KEYWORDS.get(label, [])
            # Count keyword hits with position weighting
            hits     = 0
            for kw in keywords:
                if kw in text_lower:
                    # Earlier position → higher weight
                    pos    = text_lower.find(kw)
                    weight = max(0.5, 1.0 - pos / max(len(text_lower), 1))
                    hits  += weight

            # Normalize score
            scores[label] = min(0.98, 0.05 + hits * 0.20)

        # Sort and get top-k
        sorted_labels = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_labels    = sorted_labels[:top_k]
        predicted     = top_labels[0][0] if top_labels else 'general'
        confidence    = top_labels[0][1] if top_labels else 0.10

        # Normalize all scores using softmax-like
        total = sum(scores.values()) or 1
        norm_scores = {k: round(v / total, 4) for k, v in scores.items()}

        return {
            'predicted_label':  predicted,
            'confidence':       round(confidence, 4),
            'top_labels':       [{'label': l, 'score': round(s, 4)} for l, s in top_labels],
            'all_scores':       norm_scores,
            'is_multilabel':    sum(1 for s in scores.values() if s > 0.30) > 1,
            'method':           'rule_based',
        }

    def _ml_classify(self, text: str, labels: List[str], top_k: int) -> Dict:
        """ML model based classification।"""
        try:
            pred = self._ml_model.predict([text])[0]
            prob = max(self._ml_model.predict_proba([text])[0])
            return {
                'predicted_label': pred,
                'confidence':      round(float(prob), 4),
                'method':          'ml_model',
            }
        except Exception as e:
            logger.error(f"ML classify error: {e}")
            return self._rule_classify(text, labels, top_k)

    def classify_batch(self, texts: List[str],
                        labels: List[str] = None) -> List[Dict]:
        """Batch text classification।"""
        return [self.classify(text, labels) for text in texts]

    def route_support_ticket(self, text: str) -> dict:
        """
        Customer support ticket route করো।
        Automatic department ও priority assignment।
        """
        result = self.classify(text)
        label  = result['predicted_label']

        routing = {
            'payment':      {'department': 'Finance',        'team': 'payment_support'},
            'account':      {'department': 'Account',        'team': 'account_support'},
            'technical':    {'department': 'Engineering',    'team': 'tech_support'},
            'complaint':    {'department': 'Customer Care',  'team': 'complaints'},
            'fraud_report': {'department': 'Security',       'team': 'fraud_team'},
            'offer':        {'department': 'Operations',     'team': 'offer_support'},
        }

        route    = routing.get(label, {'department': 'General', 'team': 'general_support'})
        priority = PRIORITY_MAP.get(label, 'low')

        return {
            'department':     route['department'],
            'team':           route['team'],
            'priority':       priority,
            'predicted_type': label,
            'confidence':     result['confidence'],
            'auto_reply_key': f"auto_reply_{label}",
            'sla_hours':      {'critical': 1, 'high': 4, 'medium': 24, 'low': 72}.get(priority, 72),
        }

    def detect_language(self, text: str) -> str:
        """Quick language detection।"""
        bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
        if bengali_chars / max(len(text), 1) > 0.15:
            return 'bn'
        return 'en'

    def multilabel_classify(self, text: str, threshold: float = 0.30) -> List[str]:
        """Multiple labels যেগুলো threshold এর উপরে।"""
        result = self.classify(text, top_k=len(LABEL_KEYWORDS))
        return [
            item['label'] for item in result.get('top_labels', [])
            if item['score'] >= threshold
        ]

    def confidence_calibration_check(self, predictions: List[Dict],
                                      ground_truth: List[str]) -> dict:
        """Model calibration check — confidence কতটা accurate।"""
        bins = {f"{i*10}-{(i+1)*10}%": {'count': 0, 'correct': 0}
                for i in range(10)}

        for pred, truth in zip(predictions, ground_truth):
            conf  = pred.get('confidence', 0)
            label = pred.get('predicted_label', '')
            bin_k = f"{int(conf * 10) * 10}-{int(conf * 10) * 10 + 10}%"
            if bin_k in bins:
                bins[bin_k]['count']   += 1
                bins[bin_k]['correct'] += (label == truth)

        calibration = {}
        for bin_k, data in bins.items():
            if data['count'] > 0:
                calibration[bin_k] = {
                    'count':    data['count'],
                    'accuracy': round(data['correct'] / data['count'], 4),
                }

        return {'calibration_by_confidence': calibration}

    def fine_tune_keywords(self, label: str, new_keywords: List[str]):
        """Custom keywords add করো।"""
        if label not in LABEL_KEYWORDS:
            LABEL_KEYWORDS[label] = []
        LABEL_KEYWORDS[label].extend(
            kw.lower() for kw in new_keywords if kw.lower() not in LABEL_KEYWORDS[label]
        )
        logger.info(f"Added {len(new_keywords)} keywords to '{label}'")

    def _empty_result(self) -> Dict:
        return {
            'predicted_label': 'general',
            'confidence':       0.10,
            'top_labels':       [],
            'all_scores':       {},
            'is_multilabel':    False,
            'method':           'empty_input',
        }
