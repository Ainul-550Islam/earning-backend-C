"""
api/ai_engine/NLP_ENGINES/feedback_analyzer.py
===============================================
Feedback Analyzer — user feedback comprehensive analysis।
Rating, sentiment, topics, actionable insights।
Product improvement, CX optimization।
"""
import re, logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class FeedbackAnalyzer:
    """Comprehensive user feedback analysis engine।"""

    POSITIVE_SIGNALS = [
        'good', 'great', 'excellent', 'amazing', 'love', 'best', 'helpful', 'easy',
        'fast', 'awesome', 'perfect', 'wonderful', 'fantastic', 'ভালো', 'চমৎকার',
    ]
    NEGATIVE_SIGNALS = [
        'bad', 'worst', 'terrible', 'horrible', 'slow', 'broken', 'issue', 'problem',
        'error', 'fail', 'hate', 'awful', 'poor', 'disappointing', 'খারাপ', 'সমস্যা',
    ]
    TOPIC_KEYWORDS = {
        'payment':     ['payment', 'withdraw', 'money', 'payout', 'bkash', 'nagad', 'টাকা'],
        'offers':      ['offer', 'task', 'reward', 'earn', 'অফার', 'উপার্জন'],
        'app_ux':      ['app', 'interface', 'design', 'button', 'slow', 'crash', 'bug'],
        'support':     ['support', 'help', 'response', 'team', 'service'],
        'referral':    ['referral', 'refer', 'friend', 'code', 'bonus', 'রেফার'],
        'account':     ['account', 'login', 'password', 'register', 'kyc', 'verify'],
    }

    def analyze(self, feedback: str, rating: float = None) -> dict:
        """Single feedback analyze করো।"""
        if not feedback:
            return self._empty_result()

        text_lower = feedback.lower()

        # Sentiment
        pos_count = sum(1 for w in self.POSITIVE_SIGNALS if w in text_lower)
        neg_count = sum(1 for w in self.NEGATIVE_SIGNALS if w in text_lower)
        sentiment_score = (pos_count - neg_count) / max(pos_count + neg_count, 1)

        # Rating-adjusted sentiment
        if rating is not None:
            rating_norm   = (rating - 3) / 2   # -1 to +1
            sentiment_score = sentiment_score * 0.6 + rating_norm * 0.4

        sentiment = ('positive' if sentiment_score > 0.15 else
                     'negative' if sentiment_score < -0.15 else 'neutral')

        # Topics
        detected_topics = []
        for topic, kws in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in kws):
                detected_topics.append(topic)

        # Action items
        action_items = self._extract_action_items(feedback, text_lower)

        # Priority
        priority = 'high' if sentiment == 'negative' and rating and rating <= 2 else \
                   'medium' if sentiment == 'negative' else 'low'

        return {
            'sentiment':       sentiment,
            'sentiment_score': round(sentiment_score, 4),
            'topics':          detected_topics,
            'rating':          rating,
            'word_count':      len(feedback.split()),
            'action_items':    action_items,
            'priority':        priority,
            'needs_response':  sentiment == 'negative' or (rating and rating <= 2),
        }

    def _extract_action_items(self, text: str, text_lower: str) -> List[str]:
        actions = []
        patterns = {
            'payment_issue':    any(w in text_lower for w in ['payment', 'withdraw', 'payout']),
            'bug_report':       any(w in text_lower for w in ['bug', 'crash', 'error', 'broken']),
            'feature_request':  any(w in text_lower for w in ['add', 'feature', 'wish', 'would be nice']),
            'support_needed':   any(w in text_lower for w in ['help', 'contact', 'support']),
        }
        for action, detected in patterns.items():
            if detected:
                actions.append(action)
        return actions

    def _empty_result(self) -> dict:
        return {'sentiment': 'neutral', 'sentiment_score': 0.0, 'topics': [],
                'rating': None, 'word_count': 0, 'action_items': [], 'priority': 'low'}

    def analyze_batch(self, feedbacks: List[Dict]) -> dict:
        """Multiple feedbacks analyze করে summary দাও।"""
        results = []
        for item in feedbacks:
            text   = item.get('text', '')
            rating = item.get('rating')
            result = self.analyze(text, rating)
            results.append(result)

        if not results:
            return {}

        total     = len(results)
        positive  = sum(1 for r in results if r['sentiment'] == 'positive')
        negative  = sum(1 for r in results if r['sentiment'] == 'negative')
        neutral   = total - positive - negative
        avg_score = sum(r['sentiment_score'] for r in results) / total

        # Topic frequency
        topic_counts: Dict[str, int] = {}
        for r in results:
            for topic in r['topics']:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            'total_feedback':    total,
            'positive_count':    positive,
            'negative_count':    negative,
            'neutral_count':     neutral,
            'satisfaction_rate': round(positive / total, 4),
            'avg_sentiment':     round(avg_score, 4),
            'top_topics':        dict(top_topics),
            'needs_attention':   [r for r in results if r.get('needs_response', False)][:10],
            'nps_estimate':      round((positive - negative) / total * 100, 1),
        }

    def generate_insights(self, batch_result: dict) -> List[str]:
        """Batch results থেকে actionable insights generate করো।"""
        insights = []
        sat_rate = batch_result.get('satisfaction_rate', 0.5)
        if sat_rate < 0.50:
            insights.append(f"⚠️ Low satisfaction ({sat_rate:.0%}) — immediate action needed")
        elif sat_rate > 0.80:
            insights.append(f"✅ High satisfaction ({sat_rate:.0%}) — maintain current approach")

        top_topics = batch_result.get('top_topics', {})
        for topic, count in list(top_topics.items())[:3]:
            insights.append(f"📌 Topic '{topic}' mentioned {count} times — review and optimize")

        nps = batch_result.get('nps_estimate', 0)
        insights.append(f"📊 Estimated NPS: {nps:.1f} ({'Good' if nps >= 50 else 'Needs work' if nps >= 0 else 'Poor'})")
        return insights
