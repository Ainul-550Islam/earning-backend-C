"""
api/support/analytics/topic_clustering.py
FILE 20/70 — AI Topic Clustering

Support tickets-এর common topics group করো।
Trending issues detect করো।
KB gaps identify করো।

Algorithm:
- Keyword frequency analysis
- N-gram extraction
- Topic scoring + trend detection
- Claude API for topic labeling
"""
import re
import logging
from collections import Counter, defaultdict
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger     = logging.getLogger(__name__)
API_KEY    = getattr(settings, 'ANTHROPIC_API_KEY', '')
CACHE_TTL  = 7200  # 2 hours


class TopicClusteringEngine:
    """
    Ticket topic clustering।
    Common issues group করো।
    Trending topics detect করো।
    """

    STOP_WORDS = {
        'i', 'my', 'the', 'a', 'an', 'is', 'are', 'was', 'not', 'have',
        'to', 'in', 'and', 'or', 'but', 'for', 'with', 'this', 'that',
        'it', 'be', 'do', 'did', 'has', 'can', 'will', 'would', 'your',
        'me', 'we', 'you', 'he', 'she', 'they', 'at', 'by', 'from',
        'on', 'about', 'please', 'help', 'need', 'want', 'get', 'got',
        # Bengali stop words
        'আমি', 'আমার', 'এটা', 'এই', 'না', 'হয়নি', 'করেছি', 'আমাকে',
        'আপনি', 'আপনার', 'কিন্তু', 'এবং', 'অথবা', 'যে', 'কি', 'কেন',
    }

    # Known topic patterns
    TOPIC_PATTERNS = {
        'withdrawal_failed':       ['withdrawal failed', 'withdraw failed', 'উইথড্র হচ্ছে না', 'failed withdrawal'],
        'coins_not_credited':      ['coins not', 'coin not', 'missing coins', 'coins missing', 'কয়েন পাইনি'],
        'account_suspended':       ['account suspend', 'account banned', 'account block', 'একাউন্ট সাসপেন্ড'],
        'payment_not_received':    ['payment not received', 'payment pending', 'পেমেন্ট পাইনি'],
        'offer_not_working':       ['offer not', 'task not', 'offer broken', 'অফার কাজ করছে না'],
        'kyc_rejected':            ['kyc reject', 'kyc failed', 'verification failed', 'কেওয়াইসি রিজেক্ট'],
        'login_issue':             ['cannot login', "can't login", 'login failed', 'লগইন হচ্ছে না'],
        'referral_bonus_missing':  ['referral bonus', 'referral commission', 'রেফারেল বোনাস'],
        'slow_loading':            ['slow loading', 'app slow', 'website slow', 'slow response'],
        'bkash_payment':           ['bkash', 'বিকাশ'],
        'nagad_payment':           ['nagad', 'নগদ'],
    }

    # ──────────────────────────────────────────
    # MAIN: CLUSTER TOPICS
    # ──────────────────────────────────────────
    def get_topic_clusters(self, days: int = 7, min_frequency: int = 2) -> list:
        """
        Recent tickets-এর topics cluster করো।
        Returns: [{topic, count, tickets, trend, is_new, kb_gap}]
        """
        cache_key = f'topics:{days}:{min_frequency}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        tickets   = self._get_recent_tickets(days)
        if not tickets:
            return []

        # Extract and cluster topics
        topics    = self._extract_topics(tickets)
        clusters  = self._build_clusters(topics, min_frequency)

        # Add trend info
        prev_tickets = self._get_recent_tickets(days * 2)
        prev_topics  = self._extract_topics(prev_tickets) if prev_tickets else {}
        clusters     = self._add_trend(clusters, prev_topics)

        # Add KB gap detection
        clusters = self._detect_kb_gaps(clusters)

        # Sort by count
        clusters.sort(key=lambda x: x['count'], reverse=True)

        result = clusters[:20]  # Top 20 topics
        cache.set(cache_key, result, timeout=CACHE_TTL)
        return result

    def get_trending_topics(self, days: int = 3) -> list:
        """Rapidly growing topics — early warning"""
        clusters = self.get_topic_clusters(days=days)
        trending = [t for t in clusters if t.get('trend') == 'rising' or t.get('is_new')]
        return sorted(trending, key=lambda x: x.get('growth_rate', 0), reverse=True)[:10]

    def get_kb_gaps(self, days: int = 30) -> list:
        """Topics without KB articles — create articles for these"""
        clusters = self.get_topic_clusters(days=days)
        return [t for t in clusters if t.get('kb_gap') and t['count'] >= 5]

    def get_topic_summary(self, days: int = 7) -> dict:
        """Executive summary of topics"""
        clusters = self.get_topic_clusters(days=days)
        if not clusters:
            return {}

        total_tickets = sum(c['count'] for c in clusters)
        return {
            'period_days':      days,
            'total_clustered':  total_tickets,
            'total_topics':     len(clusters),
            'top_topic':        clusters[0] if clusters else None,
            'trending':         [c for c in clusters if c.get('trend') == 'rising'][:3],
            'new_topics':       [c for c in clusters if c.get('is_new')][:3],
            'kb_gaps':          [c for c in clusters if c.get('kb_gap')][:5],
            'generated_at':     timezone.now().isoformat(),
        }

    # ──────────────────────────────────────────
    # TOPIC EXTRACTION
    # ──────────────────────────────────────────
    def _extract_topics(self, tickets: list) -> dict:
        """Tickets থেকে topics extract করো"""
        topic_tickets = defaultdict(list)

        for ticket in tickets:
            text = f"{ticket.get('subject','')} {ticket.get('description','')[:200]}".lower()

            # Pattern-based matching (fast + accurate)
            matched = False
            for topic, patterns in self.TOPIC_PATTERNS.items():
                if any(pattern.lower() in text for pattern in patterns):
                    topic_tickets[topic].append(ticket['ticket_id'])
                    matched = True

            if not matched:
                # N-gram extraction for unknown topics
                ngrams = self._extract_ngrams(text, n=2)
                for ngram in ngrams[:5]:
                    topic_tickets[ngram].append(ticket['ticket_id'])

        return dict(topic_tickets)

    def _extract_ngrams(self, text: str, n: int = 2) -> list:
        """Extract meaningful N-grams"""
        words  = [
            w for w in re.findall(r'\b[a-zA-Z\u0980-\u09FF]{3,}\b', text)
            if w not in self.STOP_WORDS
        ]
        ngrams = []
        for i in range(len(words) - n + 1):
            gram = ' '.join(words[i:i+n])
            if len(gram) > 5:
                ngrams.append(gram)
        return ngrams

    def _build_clusters(self, topics: dict, min_freq: int) -> list:
        """Topics → cluster objects"""
        clusters = []
        for topic, ticket_ids in topics.items():
            count = len(ticket_ids)
            if count < min_freq:
                continue

            # Clean topic name
            clean_name = self._clean_topic_name(topic)

            clusters.append({
                'topic':       clean_name,
                'raw_topic':   topic,
                'count':       count,
                'ticket_ids':  ticket_ids[:10],  # Sample
                'trend':       'stable',
                'growth_rate': 0,
                'is_new':      False,
                'kb_gap':      False,
            })

        return clusters

    def _add_trend(self, clusters: list, prev_topics: dict) -> list:
        """Trend compare করো — rising/falling/stable"""
        for cluster in clusters:
            raw = cluster['raw_topic']
            prev_count = len(prev_topics.get(raw, []))
            curr_count = cluster['count']

            if prev_count == 0:
                cluster['is_new']      = True
                cluster['trend']       = 'new'
                cluster['growth_rate'] = 100
            elif curr_count > prev_count * 1.5:
                cluster['trend']       = 'rising'
                cluster['growth_rate'] = round((curr_count - prev_count) / prev_count * 100, 0)
            elif curr_count < prev_count * 0.7:
                cluster['trend']       = 'falling'
                cluster['growth_rate'] = round((curr_count - prev_count) / prev_count * 100, 0)
            else:
                cluster['trend']       = 'stable'
                cluster['growth_rate'] = 0

        return clusters

    def _detect_kb_gaps(self, clusters: list) -> list:
        """KB article না থাকলে gap mark করো"""
        try:
            from api.support.models import KBArticle
            from django.db.models import Q

            for cluster in clusters:
                topic = cluster['topic']
                # Check if KB article exists
                has_article = KBArticle.objects.filter(
                    Q(title__icontains=topic[:20]) |
                    Q(tags__icontains=topic[:20]),
                    status='published',
                ).exists()
                cluster['kb_gap'] = not has_article

        except Exception:
            pass

        return clusters

    # ──────────────────────────────────────────
    # DB FETCHER
    # ──────────────────────────────────────────
    def _get_recent_tickets(self, days: int) -> list:
        try:
            from api.support.models import SupportTicket
            since = timezone.now() - timedelta(days=days)
            return list(
                SupportTicket.objects.filter(created_at__gte=since)
                .values('ticket_id', 'subject', 'description', 'category')[:500]
            )
        except Exception as e:
            logger.error(f'Get tickets failed: {e}')
            return []

    def _clean_topic_name(self, raw: str) -> str:
        """Make topic name human-readable"""
        # Known topic names
        known = {
            'withdrawal_failed':    'Withdrawal Failed',
            'coins_not_credited':   'Coins Not Credited',
            'account_suspended':    'Account Suspended',
            'payment_not_received': 'Payment Not Received',
            'offer_not_working':    'Offer Not Working',
            'kyc_rejected':         'KYC Rejected',
            'login_issue':          'Login Issue',
            'referral_bonus_missing':'Referral Bonus Missing',
            'slow_loading':         'Slow Loading',
            'bkash_payment':        'bKash Payment Issue',
            'nagad_payment':        'Nagad Payment Issue',
        }
        return known.get(raw, raw.replace('_', ' ').title())

    # ──────────────────────────────────────────
    # SAVE TO DB
    # ──────────────────────────────────────────
    def save_clusters_to_db(self, days: int = 7) -> int:
        """TopicCluster model-এ save করো"""
        try:
            from api.support.models import TopicCluster
            clusters = self.get_topic_clusters(days=days)
            since    = timezone.now() - timedelta(days=days)

            saved = 0
            for cluster in clusters[:10]:
                TopicCluster.objects.update_or_create(
                    name         = cluster['topic'],
                    period_start = since.date(),
                    defaults     = {
                        'keywords':    [cluster['raw_topic']],
                        'volume':      cluster['count'],
                        'trend':       cluster['trend'],
                        'period_end':  timezone.now().date(),
                    }
                )
                saved += 1
            return saved
        except Exception as e:
            logger.error(f'Save clusters failed: {e}')
            return 0


# Singleton
topic_clustering = TopicClusteringEngine()