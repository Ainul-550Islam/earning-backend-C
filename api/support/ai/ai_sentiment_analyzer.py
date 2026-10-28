"""
api/support/ai/ai_sentiment_analyzer.py
FILE 8/70 — AI Sentiment Analyzer

User-এর message-এর mood detect করো:
- angry/frustrated → priority upgrade + urgent flag
- sad/upset → empathetic response
- positive → normal flow
- threatening → security alert

Real-time analysis — ticket create + reply-তে।
"""
import re
import logging
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY = getattr(settings, 'ANTHROPIC_API_KEY', '')


class AISentimentAnalyzer:
    """
    Multi-layer sentiment analysis:
    Layer 1: Keyword/pattern (instant)
    Layer 2: Claude API (deep analysis for complex cases)
    """

    # ──────────────────────────────────────────
    # SENTIMENT WORD BANKS
    # ──────────────────────────────────────────
    ANGRY_WORDS = [
        # English
        'angry', 'furious', 'rage', 'outraged', 'livid', 'terrible',
        'awful', 'horrible', 'disgusting', 'unacceptable', 'useless',
        'worthless', 'pathetic', 'disgusted', 'fed up', 'ridiculous',
        'worst', 'scam', 'fraud', 'cheating', 'steal', 'robbing',
        'lawsuit', 'legal action', 'report you', 'sue you',
        # Bengali
        'রাগ', 'রাগান্বিত', 'বিরক্ত', 'ক্ষুব্ধ', 'প্রতারণা',
        'জঘন্য', 'বাজে', 'নিকৃষ্ট', 'মামলা', 'অভিযোগ',
    ]

    FRUSTRATED_WORDS = [
        # English
        'frustrated', 'disappointed', 'annoyed', 'upset', 'unhappy',
        'not happy', 'unresolved', 'still waiting', 'no response',
        'ignored', 'weeks ago', 'days ago', 'hours waiting',
        'keep asking', 'third time', 'multiple times',
        # Bengali
        'হতাশ', 'বিরক্ত', 'অপেক্ষা করছি', 'কোনো সাড়া নেই',
    ]

    POSITIVE_WORDS = [
        'thank', 'thanks', 'great', 'awesome', 'excellent', 'perfect',
        'love', 'amazing', 'wonderful', 'helpful', 'satisfied', 'happy',
        'resolved', 'fixed', 'working', 'appreciate',
        'ধন্যবাদ', 'চমৎকার', 'ভালো', 'সন্তুষ্ট',
    ]

    URGENT_PATTERNS = [
        r'\!{3,}',          # Multiple exclamation marks
        r'[A-Z]{5,}',       # ALL CAPS words
        r'URGENT|EMERGENCY|IMMEDIATELY|ASAP',
        r'জরুরী|জরুরি|এখনই|এখনি',
    ]

    THREATENING_PATTERNS = [
        r'(will|going to|gonna).{0,20}(report|sue|lawyer|court|police)',
        r'(legal action|lawsuit|attorney|solicitor)',
        r'(consumer forum|consumer court|regulatory)',
        r'(media|news|viral|social media).{0,20}(complaint|report)',
    ]

    # ──────────────────────────────────────────
    # MAIN ANALYSIS
    # ──────────────────────────────────────────
    def analyze(self, text: str, ticket=None) -> dict:
        """
        Text sentiment analyze করো।
        Returns: {
            sentiment: str,
            score: float,     # -1.0 (very negative) to 1.0 (very positive)
            emotions: list,   # ['angry', 'frustrated']
            is_urgent: bool,
            is_threatening: bool,
            urgency_score: float,
            action_required: str,  # 'escalate'/'prioritize'/'normal'/'flag'
        }
        """
        if not text:
            return self._neutral_result()

        text_lower = text.lower()

        # Sentiment scoring
        angry_score     = self._count_keywords(text_lower, self.ANGRY_WORDS)
        frustrated_score= self._count_keywords(text_lower, self.FRUSTRATED_WORDS)
        positive_score  = self._count_keywords(text_lower, self.POSITIVE_WORDS)

        # Pattern detection
        is_urgent      = self._detect_patterns(text, self.URGENT_PATTERNS)
        is_threatening = self._detect_patterns(text_lower, self.THREATENING_PATTERNS)

        # Determine emotions
        emotions = []
        if angry_score >= 2:
            emotions.append('angry')
        elif angry_score >= 1:
            emotions.append('annoyed')
        if frustrated_score >= 2:
            emotions.append('frustrated')
        if positive_score >= 2:
            emotions.append('happy')
        if is_threatening:
            emotions.append('threatening')
        if is_urgent:
            emotions.append('urgent')

        # Calculate score (-1.0 to 1.0)
        neg_total = angry_score * 2 + frustrated_score
        pos_total = positive_score
        total     = neg_total + pos_total

        if total == 0:
            score = 0.0
        else:
            score = (pos_total - neg_total) / (total + 2)  # +2 to avoid extreme values
        score = max(-1.0, min(1.0, score))

        # Determine sentiment label
        if score <= -0.5 or is_threatening:
            sentiment = 'very_negative'
        elif score <= -0.2:
            sentiment = 'negative'
        elif score <= 0.2:
            sentiment = 'neutral'
        elif score <= 0.6:
            sentiment = 'positive'
        else:
            sentiment = 'very_positive'

        # Urgency score (0.0-1.0)
        urgency_score = min(1.0, (
            (1.0 if is_urgent else 0.0) +
            (0.8 if is_threatening else 0.0) +
            (angry_score * 0.2) +
            (frustrated_score * 0.1)
        ))

        # Action determination
        action = self._determine_action(
            sentiment, is_threatening, urgency_score, ticket
        )

        result = {
            'sentiment':     sentiment,
            'score':         round(score, 3),
            'emotions':      emotions,
            'is_urgent':     is_urgent or urgency_score >= 0.7,
            'is_threatening':is_threatening,
            'urgency_score': round(urgency_score, 2),
            'action_required':action,
            'angry_signals': angry_score,
            'frustration_signals': frustrated_score,
        }

        # Apply to ticket if provided
        if ticket:
            self._apply_to_ticket(ticket, result)

        return result

    def analyze_ticket(self, ticket) -> dict:
        """Full ticket (subject + description + messages) analyze করো"""
        from api.support.models import TicketMessage

        text_parts = [ticket.subject, ticket.description]

        # Latest user messages
        messages = TicketMessage.objects.filter(
            ticket   = ticket,
            is_agent = False,
        ).order_by('-created_at')[:3]

        for msg in messages:
            text_parts.append(msg.content)

        full_text = ' '.join(text_parts)
        return self.analyze(full_text, ticket)

    def analyze_message(self, message_content: str, ticket=None) -> dict:
        """Single message analyze করো"""
        return self.analyze(message_content, ticket)

    # ──────────────────────────────────────────
    # REAL-TIME MONITORING
    # ──────────────────────────────────────────
    def monitor_conversation(self, ticket_id: str) -> dict:
        """
        Conversation-এর sentiment trend দেখাও।
        Agent dashboard-এ real-time দেখা যাবে।
        """
        from api.support.models import TicketMessage

        messages = TicketMessage.objects.filter(
            ticket__ticket_id = ticket_id,
            is_agent          = False,
        ).order_by('created_at')[:20]

        trend  = []
        prev   = 0.0
        for msg in messages:
            result = self.analyze(msg.content)
            trend.append({
                'time':      msg.created_at.isoformat(),
                'score':     result['score'],
                'sentiment': result['sentiment'],
                'delta':     round(result['score'] - prev, 2),
            })
            prev = result['score']

        # Overall trend
        if len(trend) >= 2:
            first_half = sum(t['score'] for t in trend[:len(trend)//2]) / (len(trend)//2)
            last_half  = sum(t['score'] for t in trend[len(trend)//2:]) / max(len(trend)//2, 1)
            direction  = 'improving' if last_half > first_half else 'declining' if last_half < first_half else 'stable'
        else:
            direction = 'insufficient_data'

        return {
            'ticket_id':  ticket_id,
            'trend':      trend,
            'direction':  direction,
            'latest':     trend[-1] if trend else {},
            'risk_level': self._calculate_risk(trend),
        }

    def get_high_risk_tickets(self, limit: int = 20) -> list:
        """High frustration/anger tickets — agent dashboard-এ দেখাবে"""
        from api.support.models import SupportTicket

        tickets = SupportTicket.objects.filter(
            status__in=['open', 'in_progress', 'waiting_user'],
        ).select_related('user', 'assigned_to').order_by('-created_at')[:100]

        high_risk = []
        for ticket in tickets:
            text   = f"{ticket.subject} {ticket.description}"
            result = self.analyze(text)
            if result['urgency_score'] >= 0.5 or result['is_threatening']:
                high_risk.append({
                    'ticket_id':    ticket.ticket_id,
                    'subject':      ticket.subject[:60],
                    'user':         ticket.user.username,
                    'sentiment':    result['sentiment'],
                    'urgency_score':result['urgency_score'],
                    'emotions':     result['emotions'],
                    'is_threatening':result['is_threatening'],
                })

        return sorted(high_risk, key=lambda x: x['urgency_score'], reverse=True)[:limit]

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────
    def _count_keywords(self, text: str, keywords: list) -> int:
        return sum(1 for kw in keywords if kw.lower() in text)

    def _detect_patterns(self, text: str, patterns: list) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _determine_action(self, sentiment: str, is_threatening: bool, urgency: float, ticket) -> str:
        if is_threatening:
            return 'flag'  # Flag for security + management review
        if urgency >= 0.8 or sentiment == 'very_negative':
            return 'escalate'  # Auto-escalate
        if urgency >= 0.5 or sentiment == 'negative':
            return 'prioritize'  # Increase priority
        return 'normal'

    def _apply_to_ticket(self, ticket, result: dict) -> None:
        """Sentiment result ticket-এ apply করো"""
        try:
            update_fields = []

            # Update sentiment
            ticket.ai_sentiment = result['sentiment']
            update_fields.append('ai_sentiment')

            # Auto-escalate on extreme negativity
            if result['action_required'] == 'escalate' and not ticket.escalated:
                ticket.escalated    = True
                ticket.escalated_at = timezone.now()
                update_fields.extend(['escalated', 'escalated_at'])

            # Upgrade priority for angry/threatening users
            if result['action_required'] in ['escalate', 'prioritize']:
                priority_map = {'low': 'medium', 'medium': 'high', 'high': 'urgent'}
                new_priority = priority_map.get(ticket.priority, ticket.priority)
                if new_priority != ticket.priority:
                    ticket.priority = new_priority
                    update_fields.append('priority')

            if update_fields:
                ticket.save(update_fields=list(set(update_fields)))

        except Exception as e:
            logger.warning(f'Apply sentiment to ticket failed: {e}')

    def _calculate_risk(self, trend: list) -> str:
        if not trend:
            return 'unknown'
        latest_score = trend[-1]['score'] if trend else 0
        if latest_score <= -0.6:
            return 'high'
        if latest_score <= -0.3:
            return 'medium'
        return 'low'

    def _neutral_result(self) -> dict:
        return {
            'sentiment': 'neutral', 'score': 0.0, 'emotions': [],
            'is_urgent': False, 'is_threatening': False,
            'urgency_score': 0.0, 'action_required': 'normal',
            'angry_signals': 0, 'frustration_signals': 0,
        }


# Singleton
sentiment_analyzer = AISentimentAnalyzer()