# =============================================================================
# api/promotions/data_science/recommendation_engine.py
# Recommendation Engine — User কে কোন tasks দেখালে সে বেশি complete করবে
# Collaborative Filtering + Content-Based + Hybrid approach
# =============================================================================

import logging
import math
from dataclasses import dataclass, field
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('data_science.recommendation')
CACHE_PREFIX_REC = 'ds:rec:{}'


@dataclass
class CampaignRecommendation:
    campaign_id:      int
    score:            float       # 0.0 - 1.0
    reason:           str         # Why recommended?
    expected_approval_rate: float
    platform:         str
    reward_usd:       float


@dataclass
class RecommendationResult:
    user_id:         int
    recommendations: list        # List of CampaignRecommendation
    strategy_used:   str
    generated_at:    float


class RecommendationEngine:
    """
    Hybrid Recommendation System।

    Strategies:
    1. Content-Based: User এর past completed tasks এর সাথে similar campaigns
    2. Collaborative: Similar users যা করেছে তা suggest করা
    3. Performance-Based: User এর approval rate বেশি যে platforms এ
    4. Trending: এই সপ্তাহে সবচেয়ে popular campaigns
    5. New User (Cold Start): High approval rate campaigns

    Scoring formula:
    score = 0.35 * content_sim + 0.25 * collab_score + 0.25 * performance + 0.15 * trending
    """

    WEIGHTS = {
        'content_similarity': 0.35,
        'collaborative':      0.25,
        'performance':        0.25,
        'trending':           0.15,
    }

    def recommend_for_user(self, user_id: int, limit: int = 10) -> RecommendationResult:
        """User এর জন্য top campaigns recommend করে।"""
        import time
        cache_key = CACHE_PREFIX_REC.format(f'user:{user_id}:{limit}')
        cached    = cache.get(cache_key)
        if cached:
            return RecommendationResult(**cached)

        # User history check
        user_profile = self._get_user_profile(user_id)

        if not user_profile['total_tasks']:
            # Cold start — new user
            recs     = self._cold_start_recommendations(limit)
            strategy = 'cold_start'
        else:
            recs     = self._hybrid_recommendations(user_id, user_profile, limit)
            strategy = 'hybrid'

        result = RecommendationResult(
            user_id=user_id, recommendations=recs,
            strategy_used=strategy, generated_at=time.time(),
        )
        cache.set(cache_key, {
            'user_id': result.user_id,
            'recommendations': [r.__dict__ for r in result.recommendations],
            'strategy_used': result.strategy_used,
            'generated_at': result.generated_at,
        }, timeout=1800)   # 30 min cache

        return result

    def get_similar_campaigns(self, campaign_id: int, limit: int = 5) -> list:
        """Similar campaigns (content-based)।"""
        try:
            from api.promotions.models import Campaign
            from api.promotions.choices import CampaignStatus
            target = Campaign.objects.select_related('platform', 'category').get(pk=campaign_id)

            similar = Campaign.objects.filter(
                status=CampaignStatus.ACTIVE,
                platform=target.platform,
            ).exclude(pk=campaign_id).select_related('platform', 'category')[:limit*2]

            scored = []
            for c in similar:
                sim = self._content_similarity(target, c)
                scored.append(CampaignRecommendation(
                    campaign_id=c.id, score=sim, reason='Similar to current campaign',
                    expected_approval_rate=0.7, platform=c.platform.name,
                    reward_usd=float(c.reward_per_task_usd or 0),
                ))
            scored.sort(key=lambda x: x.score, reverse=True)
            return scored[:limit]
        except Exception as e:
            logger.debug(f'Similar campaigns failed: {e}')
            return []

    def update_user_interaction(
        self, user_id: int, campaign_id: int, interaction: str
    ) -> None:
        """
        User interaction record করে (implicit feedback)।
        interaction: 'view', 'start', 'complete', 'skip'
        """
        key     = CACHE_PREFIX_REC.format(f'interactions:{user_id}')
        history = cache.get(key) or []
        history.append({'campaign_id': campaign_id, 'interaction': interaction})
        history = history[-100:]  # Last 100 interactions
        cache.set(key, history, timeout=86400 * 30)
        # Invalidate recommendations cache
        cache.delete(CACHE_PREFIX_REC.format(f'user:{user_id}:10'))

    # ── Strategies ────────────────────────────────────────────────────────────

    def _cold_start_recommendations(self, limit: int) -> list:
        """New user — high approval rate campaigns দেখাও।"""
        try:
            from api.promotions.models import Campaign, TaskSubmission
            from api.promotions.choices import CampaignStatus, SubmissionStatus
            from django.db.models import Count, Q

            campaigns = Campaign.objects.filter(
                status=CampaignStatus.ACTIVE,
            ).annotate(
                approved=Count('submissions', filter=Q(submissions__status=SubmissionStatus.APPROVED)),
                total=Count('submissions'),
            ).select_related('platform', 'category')[:limit*2]

            recs = []
            for c in campaigns:
                rate = c.approved / max(c.total, 1)
                recs.append(CampaignRecommendation(
                    campaign_id=c.id, score=round(0.5 + rate * 0.5, 3),
                    reason='Popular with high approval rate',
                    expected_approval_rate=round(rate, 3),
                    platform=c.platform.name if c.platform else '',
                    reward_usd=float(c.reward_per_task_usd or 0),
                ))
            recs.sort(key=lambda x: x.score, reverse=True)
            return recs[:limit]
        except Exception:
            return []

    def _hybrid_recommendations(self, user_id: int, profile: dict, limit: int) -> list:
        """Hybrid scoring — content + collaborative + performance + trending।"""
        try:
            from api.promotions.models import Campaign
            from api.promotions.choices import CampaignStatus

            candidates = Campaign.objects.filter(
                status=CampaignStatus.ACTIVE,
            ).exclude(
                submissions__worker_id=user_id,
            ).select_related('platform', 'category')[:50]

            recs = []
            for c in candidates:
                content_score  = self._content_score(c, profile)
                perf_score     = profile.get('platform_scores', {}).get(
                    c.platform.name if c.platform else '', 0.5)
                trending_score = self._trending_score(c.id)
                final          = (
                    content_score  * self.WEIGHTS['content_similarity'] +
                    perf_score     * self.WEIGHTS['performance'] +
                    trending_score * self.WEIGHTS['trending']
                )
                recs.append(CampaignRecommendation(
                    campaign_id=c.id, score=round(final, 3),
                    reason=self._explain_score(content_score, perf_score, trending_score),
                    expected_approval_rate=round(perf_score, 3),
                    platform=c.platform.name if c.platform else '',
                    reward_usd=float(c.reward_per_task_usd or 0),
                ))

            recs.sort(key=lambda x: x.score, reverse=True)
            return recs[:limit]
        except Exception as e:
            logger.debug(f'Hybrid rec failed: {e}')
            return self._cold_start_recommendations(limit)

    def _get_user_profile(self, user_id: int) -> dict:
        """User এর past performance profile।"""
        profile = {'total_tasks': 0, 'preferred_platforms': [], 'platform_scores': {}}
        try:
            from api.promotions.models import TaskSubmission
            from api.promotions.choices import SubmissionStatus
            from django.db.models import Count, Q

            platform_stats = (
                TaskSubmission.objects
                .filter(worker_id=user_id)
                .values('campaign__platform__name')
                .annotate(
                    total=Count('id'),
                    approved=Count('id', filter=Q(status=SubmissionStatus.APPROVED)),
                )
            )
            total = 0
            scores = {}
            for s in platform_stats:
                plat  = s['campaign__platform__name'] or 'unknown'
                rate  = s['approved'] / max(s['total'], 1)
                scores[plat] = rate
                total += s['total']

            profile['total_tasks']      = total
            profile['platform_scores']  = scores
            profile['preferred_platforms'] = sorted(scores, key=scores.get, reverse=True)[:3]
        except Exception:
            pass
        return profile

    @staticmethod
    def _content_score(campaign, profile: dict) -> float:
        platform = campaign.platform.name if campaign.platform else ''
        if platform in profile.get('preferred_platforms', []):
            return 0.8
        return 0.4

    @staticmethod
    def _trending_score(campaign_id: int) -> float:
        key = CACHE_PREFIX_REC.format(f'trending:{campaign_id}')
        return cache.get(key) or 0.5

    @staticmethod
    def _content_similarity(c1, c2) -> float:
        score = 0.0
        if c1.platform == c2.platform:   score += 0.5
        if c1.category == c2.category:   score += 0.5
        return score

    @staticmethod
    def _explain_score(content: float, perf: float, trending: float) -> str:
        if perf > 0.8:   return 'High approval rate on this platform'
        if content > 0.6: return 'Matches your task history'
        if trending > 0.7: return 'Trending this week'
        return 'Recommended for you'
