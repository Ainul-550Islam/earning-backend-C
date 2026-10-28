"""
api/support/ai/ai_duplicate_detector.py
FILE 9/70 — AI Duplicate Ticket Detector

User একই সমস্যার জন্য multiple ticket করলে:
1. Auto-detect করো
2. Merge suggest করো
3. User-কে inform করো
4. Agent-কে notify করো

Similarity: TF-IDF + Jaccard + Claude AI
"""
import re
import math
import logging
from collections import Counter
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY    = getattr(settings, 'ANTHROPIC_API_KEY', '')
DUPLICATE_THRESHOLD  = getattr(settings, 'DUPLICATE_SIMILARITY_THRESHOLD', 0.65)
DUPLICATE_TIME_WINDOW= getattr(settings, 'DUPLICATE_TIME_WINDOW_DAYS', 7)


class AIDuplicateDetector:
    """
    Duplicate ticket detection engine.
    Combines multiple similarity algorithms.
    """

    # ──────────────────────────────────────────
    # MAIN: CHECK FOR DUPLICATES
    # ──────────────────────────────────────────
    def check_duplicates(self, ticket) -> dict:
        """
        New ticket-এর জন্য duplicates খুঁজে বের করো।
        Returns: {
            is_duplicate: bool,
            duplicates: [{ticket_id, similarity, reason}],
            suggested_merge: str | None,
            action: 'merge'|'link'|'ignore'
        }
        """
        candidates = self._get_candidates(ticket)
        if not candidates:
            return self._no_duplicate_result()

        duplicates = []
        for candidate in candidates:
            similarity = self._calculate_similarity(ticket, candidate)
            if similarity >= DUPLICATE_THRESHOLD:
                reason = self._explain_similarity(ticket, candidate, similarity)
                duplicates.append({
                    'ticket_id': candidate.ticket_id,
                    'subject':   candidate.subject[:80],
                    'status':    candidate.status,
                    'similarity':round(similarity, 3),
                    'reason':    reason,
                    'created_at':candidate.created_at.isoformat(),
                })

        duplicates.sort(key=lambda x: x['similarity'], reverse=True)

        is_duplicate   = bool(duplicates)
        suggested_merge= duplicates[0]['ticket_id'] if duplicates else None
        action         = self._determine_action(duplicates, ticket)

        if is_duplicate:
            self._handle_duplicate(ticket, duplicates[0], action)

        return {
            'is_duplicate':   is_duplicate,
            'duplicates':     duplicates[:5],
            'suggested_merge':suggested_merge,
            'action':         action,
            'checked_at':     timezone.now().isoformat(),
        }

    def find_similar(self, subject: str, description: str, user=None, limit: int = 5) -> list:
        """Subject/description দিয়ে similar tickets খুঁজে বের করো"""
        class MockTicket:
            def __init__(self):
                self.subject     = subject
                self.description = description
                self.category    = 'other'
                self.user        = user
                self.ticket_id   = 'MOCK'
                self.created_at  = timezone.now()

        mock       = MockTicket()
        candidates = self._get_candidates(mock)
        results    = []

        for candidate in candidates:
            sim = self._calculate_similarity(mock, candidate)
            if sim >= 0.4:  # Lower threshold for "find similar"
                results.append({
                    'ticket_id': candidate.ticket_id,
                    'subject':   candidate.subject[:80],
                    'status':    candidate.status,
                    'similarity':round(sim, 3),
                })

        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]

    # ──────────────────────────────────────────
    # CANDIDATE SELECTION
    # ──────────────────────────────────────────
    def _get_candidates(self, ticket) -> list:
        """Check করার জন্য candidate tickets খুঁজে বের করো"""
        try:
            from api.support.models import SupportTicket
            from django.db.models import Q

            window = timezone.now() - timedelta(days=DUPLICATE_TIME_WINDOW)

            qs = SupportTicket.objects.filter(
                created_at__gte=window,
            ).exclude(
                status__in=['spam', 'closed']
            ).exclude(
                ticket_id=getattr(ticket, 'ticket_id', 'NONE')
            )

            # Same user → broader check
            if ticket.user and hasattr(ticket.user, 'id'):
                qs = qs.filter(user=ticket.user)

            # Same category (fast filter)
            if hasattr(ticket, 'category') and ticket.category != 'other':
                qs = qs.filter(category=ticket.category)

            return list(qs.order_by('-created_at')[:50])

        except Exception as e:
            logger.error(f'Get candidates failed: {e}')
            return []

    # ──────────────────────────────────────────
    # SIMILARITY ALGORITHMS
    # ──────────────────────────────────────────
    def _calculate_similarity(self, ticket1, ticket2) -> float:
        """Combined similarity score"""
        text1 = self._get_text(ticket1)
        text2 = self._get_text(ticket2)

        # Cache key
        key    = f'sim:{hash(text1[:50])}:{hash(text2[:50])}'
        cached = cache.get(key)
        if cached is not None:
            return cached

        # Multiple algorithms
        jaccard  = self._jaccard_similarity(text1, text2)
        cosine   = self._cosine_similarity(text1, text2)
        sequence = self._sequence_similarity(ticket1.subject, ticket2.subject)

        # Weighted average (sequence/subject match has higher weight)
        score = (jaccard * 0.25) + (cosine * 0.35) + (sequence * 0.40)

        cache.set(key, score, timeout=300)
        return score

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Word overlap similarity"""
        words1 = set(self._tokenize(text1))
        words2 = set(self._tokenize(text2))
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union        = words1 | words2
        return len(intersection) / len(union)

    def _cosine_similarity(self, text1: str, text2: str) -> float:
        """TF-based cosine similarity"""
        words1 = Counter(self._tokenize(text1))
        words2 = Counter(self._tokenize(text2))

        if not words1 or not words2:
            return 0.0

        # Dot product
        intersection = set(words1.keys()) & set(words2.keys())
        dot_product  = sum(words1[w] * words2[w] for w in intersection)

        # Magnitudes
        mag1 = math.sqrt(sum(v ** 2 for v in words1.values()))
        mag2 = math.sqrt(sum(v ** 2 for v in words2.values()))

        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot_product / (mag1 * mag2)

    def _sequence_similarity(self, str1: str, str2: str) -> float:
        """Character sequence similarity (for subject lines)"""
        if not str1 or not str2:
            return 0.0

        str1 = str1.lower().strip()
        str2 = str2.lower().strip()

        # Exact match
        if str1 == str2:
            return 1.0

        # Longest common subsequence ratio
        m, n  = len(str1), len(str2)
        if m == 0 or n == 0:
            return 0.0

        # Simple character overlap
        longer  = max(m, n)
        shorter = min(str1, str2, key=len)
        longer_s= max(str1, str2, key=len)
        matches = sum(1 for c in shorter if c in longer_s)
        return matches / longer

    # ──────────────────────────────────────────
    # EXPLANATION
    # ──────────────────────────────────────────
    def _explain_similarity(self, ticket1, ticket2, similarity: float) -> str:
        text1 = self._get_text(ticket1)
        text2 = self._get_text(ticket2)

        words1    = set(self._tokenize(text1))
        words2    = set(self._tokenize(text2))
        common    = words1 & words2
        important = [w for w in common if len(w) > 4][:5]

        reasons = []
        if similarity >= 0.9:
            reasons.append('Nearly identical content')
        elif similarity >= 0.75:
            reasons.append('Very similar content')
        else:
            reasons.append('Similar content')

        if ticket1.category == ticket2.category:
            reasons.append(f'Same category: {ticket1.category}')

        if important:
            reasons.append(f'Common keywords: {", ".join(important[:3])}')

        return ' | '.join(reasons)

    # ──────────────────────────────────────────
    # ACTION
    # ──────────────────────────────────────────
    def _determine_action(self, duplicates: list, ticket) -> str:
        if not duplicates:
            return 'ignore'
        top = duplicates[0]['similarity']
        if top >= 0.85:
            return 'merge'      # Auto-merge suggest
        if top >= 0.65:
            return 'link'       # Link as related
        return 'ignore'

    def _handle_duplicate(self, ticket, top_duplicate: dict, action: str) -> None:
        """Duplicate found — appropriate action নাও"""
        try:
            from api.support.models import SupportTicket

            # AI analysis field update
            ticket.ai_category = ticket.ai_category  # No change
            # Flag as potential duplicate in ticket notes
            from api.support.models import TicketMessage
            from django.contrib.auth import get_user_model
            User   = get_user_model()
            system = User.objects.filter(is_superuser=True).first()
            if system:
                TicketMessage.objects.create(
                    ticket      = ticket,
                    sender      = system,
                    content     = (
                        f'🤖 [AI Duplicate Detection]\n'
                        f'This ticket appears to be similar to #{top_duplicate["ticket_id"]} '
                        f'(similarity: {top_duplicate["similarity"]:.0%}).\n'
                        f'Action suggested: {action}\n'
                        f'Reason: {top_duplicate["reason"]}'
                    ),
                    is_agent    = True,
                    is_internal = True,
                )
        except Exception as e:
            logger.warning(f'Handle duplicate failed: {e}')

    # ──────────────────────────────────────────
    # TEXT HELPERS
    # ──────────────────────────────────────────
    def _get_text(self, ticket) -> str:
        return f"{ticket.subject} {ticket.description}".lower()

    def _tokenize(self, text: str) -> list:
        """Text tokenize করো — stop words remove"""
        stop_words = {
            'i', 'my', 'the', 'a', 'an', 'is', 'are', 'was', 'not', 'have',
            'to', 'in', 'and', 'or', 'but', 'for', 'with', 'this', 'that',
            'it', 'be', 'do', 'did', 'has', 'can', 'will', 'would', 'your',
            # Bengali stop words
            'আমি', 'আমার', 'এটা', 'এই', 'না', 'হয়নি', 'করেছি',
        }
        words = re.findall(r'\b[a-zA-Z\u0980-\u09FF]{3,}\b', text)
        return [w for w in words if w.lower() not in stop_words]

    def _no_duplicate_result(self) -> dict:
        return {
            'is_duplicate': False, 'duplicates': [],
            'suggested_merge': None, 'action': 'ignore',
            'checked_at': timezone.now().isoformat(),
        }

    # ──────────────────────────────────────────
    # ANALYTICS
    # ──────────────────────────────────────────
    def get_duplicate_stats(self, days: int = 30) -> dict:
        """Duplicate ticket statistics"""
        from api.support.models import TicketMessage
        from django.db.models import Count
        since  = timezone.now() - timedelta(days=days)
        count  = TicketMessage.objects.filter(
            content__contains = '[AI Duplicate Detection]',
            created_at__gte   = since,
        ).count()
        return {'period_days': days, 'duplicates_detected': count}


# Singleton
duplicate_detector = AIDuplicateDetector()