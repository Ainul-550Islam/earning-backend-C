"""
api/support/ai/ai_churn_predictor.py
FILE 10/70 — AI Churn Risk Predictor

Frustrated/unhappy user detect করো before তারা চলে যায়।
High-risk users → priority support দাও।

Signals:
- Multiple unresolved tickets
- Negative sentiment trend
- Long wait times
- Low CSAT scores
- Threatening language
- Sudden inactivity after complaints
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AIChurnPredictor:
    """
    User churn risk scoring।
    Score 0.0-1.0 (1.0 = highest risk)।
    """

    CACHE_TTL = 3600  # 1 hour

    # Risk factor weights
    WEIGHTS = {
        'unresolved_tickets':  0.25,   # Open tickets count
        'negative_sentiment':  0.20,   # Sentiment score
        'sla_breaches':        0.15,   # SLA breach count
        'long_wait_time':      0.15,   # Avg response time
        'low_csat':            0.10,   # CSAT score
        'threatening_language':0.10,   # Threatening messages
        'repeat_complaints':   0.05,   # Same issue multiple times
    }

    # ──────────────────────────────────────────
    # MAIN: SCORE USER
    # ──────────────────────────────────────────
    def score_user(self, user) -> dict:
        """
        Single user-এর churn risk score করো।
        Returns: {
            score: float,       # 0.0-1.0
            risk_level: str,    # low/medium/high/critical
            factors: dict,      # Individual factor scores
            recommendations: list,  # What to do
            should_alert: bool,
        }
        """
        cache_key = f'churn_score:{user.id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        factors = self._calculate_factors(user)
        score   = self._calculate_score(factors)
        level   = self._get_risk_level(score)
        recs    = self._get_recommendations(score, factors, level)

        result = {
            'user_id':       str(user.id),
            'username':      user.username,
            'score':         round(score, 3),
            'risk_level':    level,
            'factors':       factors,
            'recommendations':recs,
            'should_alert':  score >= 0.7,
            'calculated_at': timezone.now().isoformat(),
        }

        cache.set(cache_key, result, timeout=self.CACHE_TTL)

        # Alert if high risk
        if result['should_alert']:
            self._send_alert(user, result)

        return result

    def score_by_ticket(self, ticket) -> dict:
        """Ticket-এর user score করো"""
        return self.score_user(ticket.user)

    # ──────────────────────────────────────────
    # FACTOR CALCULATIONS
    # ──────────────────────────────────────────
    def _calculate_factors(self, user) -> dict:
        """Individual risk factors calculate করো"""
        factors = {}
        since_30 = timezone.now() - timedelta(days=30)

        try:
            from api.support.models import SupportTicket, TicketRating, TicketMessage

            tickets_30 = SupportTicket.objects.filter(user=user, created_at__gte=since_30)

            # 1. Unresolved tickets score
            unresolved = tickets_30.filter(status__in=['open', 'in_progress', 'waiting_user']).count()
            factors['unresolved_tickets'] = min(1.0, unresolved / 3.0)

            # 2. Negative sentiment
            negative_msgs = TicketMessage.objects.filter(
                ticket__user = user,
                ticket__created_at__gte = since_30,
                is_agent     = False,
            ).count()

            from api.support.ai.ai_sentiment_analyzer import sentiment_analyzer
            if negative_msgs > 0:
                # Sample last 5 messages
                recent_msgs = TicketMessage.objects.filter(
                    ticket__user = user,
                    is_agent     = False,
                ).order_by('-created_at')[:5]

                sentiment_scores = []
                for msg in recent_msgs:
                    result = sentiment_analyzer.analyze(msg.content)
                    sentiment_scores.append(result['score'])

                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
                # Convert -1.0-1.0 to 0.0-1.0 risk (negative = high risk)
                factors['negative_sentiment'] = max(0, -avg_sentiment)
            else:
                factors['negative_sentiment'] = 0.0

            # 3. SLA breaches
            sla_breaches = tickets_30.filter(escalated=True).count()
            factors['sla_breaches'] = min(1.0, sla_breaches / 2.0)

            # 4. Long wait time
            resolved_tickets = tickets_30.filter(
                resolved_at__isnull=False,
                admin_responded_at__isnull=False,
            )
            if resolved_tickets.exists():
                wait_times = []
                for t in resolved_tickets:
                    wait_hrs = (t.admin_responded_at - t.created_at).total_seconds() / 3600
                    wait_times.append(wait_hrs)
                avg_wait = sum(wait_times) / len(wait_times)
                # > 48 hrs = high risk
                factors['long_wait_time'] = min(1.0, avg_wait / 48.0)
            else:
                factors['long_wait_time'] = 0.0

            # 5. Low CSAT score
            ratings = TicketRating.objects.filter(
                ticket__user    = user,
                created_at__gte = since_30,
            )
            if ratings.exists():
                from django.db.models import Avg
                avg_rating = ratings.aggregate(avg=Avg('rating'))['avg'] or 5
                # 5 = best, 1 = worst → invert for risk
                factors['low_csat'] = max(0, (5 - avg_rating) / 4.0)
            else:
                factors['low_csat'] = 0.0

            # 6. Threatening language
            threatening_count = 0
            recent_msgs = TicketMessage.objects.filter(
                ticket__user = user,
                is_agent     = False,
                created_at__gte = since_30,
            )[:20]

            import re
            threat_patterns = [
                r'(will|going to).{0,20}(report|sue|lawyer)',
                r'(legal|media|social media).{0,20}(complaint|report)',
                r'consumer.{0,10}(court|forum)',
            ]
            for msg in recent_msgs:
                for pattern in threat_patterns:
                    if re.search(pattern, msg.content, re.IGNORECASE):
                        threatening_count += 1
                        break

            factors['threatening_language'] = min(1.0, threatening_count / 2.0)

            # 7. Repeat complaints (same category multiple times)
            categories = list(tickets_30.values_list('category', flat=True))
            if categories:
                from collections import Counter
                cat_counts = Counter(categories)
                max_repeat = max(cat_counts.values())
                factors['repeat_complaints'] = min(1.0, (max_repeat - 1) / 3.0)
            else:
                factors['repeat_complaints'] = 0.0

        except Exception as e:
            logger.error(f'Churn factor calculation failed for user {user.id}: {e}')
            factors = {k: 0.0 for k in self.WEIGHTS}

        return factors

    def _calculate_score(self, factors: dict) -> float:
        """Weighted score calculate করো"""
        score = sum(
            factors.get(factor, 0.0) * weight
            for factor, weight in self.WEIGHTS.items()
        )
        return min(1.0, max(0.0, score))

    def _get_risk_level(self, score: float) -> str:
        if score >= 0.75:
            return 'critical'
        if score >= 0.50:
            return 'high'
        if score >= 0.25:
            return 'medium'
        return 'low'

    def _get_recommendations(self, score: float, factors: dict, level: str) -> list:
        """What to do with high-risk user"""
        recs = []

        if factors.get('unresolved_tickets', 0) >= 0.5:
            recs.append('Immediately resolve all open tickets')

        if factors.get('negative_sentiment', 0) >= 0.5:
            recs.append('Assign senior agent — user is very frustrated')

        if factors.get('sla_breaches', 0) >= 0.5:
            recs.append('Acknowledge SLA failures and offer compensation')

        if factors.get('long_wait_time', 0) >= 0.5:
            recs.append('Priority response required — user waited too long')

        if factors.get('low_csat', 0) >= 0.5:
            recs.append('Follow up on recent negative ratings')

        if factors.get('threatening_language', 0) > 0:
            recs.append('URGENT: User has used threatening language — management review required')

        if factors.get('repeat_complaints', 0) >= 0.5:
            recs.append('Identify root cause of recurring issues')

        if level == 'critical':
            recs.insert(0, '🚨 CRITICAL: Immediate VIP support intervention needed')
        elif level == 'high':
            recs.insert(0, '⚠️ HIGH RISK: Proactive outreach recommended within 24 hours')

        return recs

    # ──────────────────────────────────────────
    # BATCH SCORING
    # ──────────────────────────────────────────
    def get_high_risk_users(self, limit: int = 50) -> list:
        """High-risk users list করো — dashboard-এ দেখাবে"""
        from api.support.models import SupportTicket
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        User = get_user_model()

        # Active users with recent tickets
        active_users = User.objects.filter(
            support_supportticket_user__created_at__gte=timezone.now() - timedelta(days=30),
        ).annotate(
            ticket_count=Count('support_supportticket_user')
        ).filter(ticket_count__gte=2).distinct()[:100]

        results = []
        for user in active_users:
            score_data = self.score_user(user)
            if score_data['score'] >= 0.3:
                results.append({
                    'user_id':    str(user.id),
                    'username':   user.username,
                    'email':      user.email,
                    'score':      score_data['score'],
                    'risk_level': score_data['risk_level'],
                    'top_factors': [
                        k for k, v in sorted(
                            score_data['factors'].items(),
                            key=lambda x: x[1], reverse=True
                        )[:3] if v > 0.2
                    ],
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    def run_daily_scan(self) -> dict:
        """Daily churn risk scan — Celery task"""
        high_risk = self.get_high_risk_users(limit=50)
        critical  = [u for u in high_risk if u['risk_level'] == 'critical']
        high      = [u for u in high_risk if u['risk_level'] == 'high']

        if critical:
            logger.warning(f'CHURN ALERT: {len(critical)} critical risk users found!')
            # Notify management via Slack/Telegram

        return {
            'scanned':  len(high_risk),
            'critical': len(critical),
            'high':     len(high),
            'run_at':   timezone.now().isoformat(),
        }

    def _send_alert(self, user, score_data: dict) -> None:
        """High-risk user alert পাঠাও"""
        try:
            logger.warning(
                f'CHURN RISK: user={user.username}, '
                f'score={score_data["score"]:.2f}, '
                f'level={score_data["risk_level"]}'
            )
            # Slack/Telegram notification
        except Exception:
            pass


# Singleton
churn_predictor = AIChurnPredictor()