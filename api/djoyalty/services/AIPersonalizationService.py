# api/djoyalty/services/AIPersonalizationService.py
"""
AIPersonalizationService -- AI-powered loyalty personalization।
RFM scoring, churn prediction, personalized offers, recommendations।

World reference: Kognitiv Pulse (95%+ churn accuracy),
Antavo AI Loyalty Cloud, Starbucks AI, Ulta Beauty Ultamate।
2025 research: AI personalization = 35% higher redemption rates।
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Max, Q

logger = logging.getLogger(__name__)


class AIPersonalizationService:

    # ─── RFM SCORING ─────────────────────────────────────────────────

    @staticmethod
    def compute_rfm_score(customer, tenant=None) -> dict:
        """
        Customer এর RFM (Recency, Frequency, Monetary) score compute করো।
        Returns dict with scores and segment।
        """
        from ..models.core import Txn
        from ..models.points import LoyaltyPoints

        now = timezone.now()

        # Recency -- days since last purchase
        last_txn = Txn.objects.filter(customer=customer, value__gt=0).order_by('-timestamp').first()
        if last_txn:
            days_ago = (now - last_txn.timestamp).days
        else:
            days_ago = 9999

        recency_score = (
            5 if days_ago <= 7 else
            4 if days_ago <= 30 else
            3 if days_ago <= 90 else
            2 if days_ago <= 180 else
            1
        )

        # Frequency -- transaction count in last 90 days
        freq_count = Txn.objects.filter(
            customer=customer, value__gt=0,
            timestamp__gte=now - timedelta(days=90),
        ).count()

        frequency_score = (
            5 if freq_count >= 20 else
            4 if freq_count >= 10 else
            3 if freq_count >= 5 else
            2 if freq_count >= 2 else
            1
        )

        # Monetary -- total spend
        total_spend = Txn.objects.filter(customer=customer, value__gt=0).aggregate(
            s=Sum('value')
        )['s'] or Decimal('0')

        monetary_score = (
            5 if total_spend >= 50000 else
            4 if total_spend >= 10000 else
            3 if total_spend >= 3000 else
            2 if total_spend >= 500 else
            1
        )

        rfm_total = recency_score + frequency_score + monetary_score

        # RFM Segment
        segment = AIPersonalizationService._get_rfm_segment(
            recency_score, frequency_score, monetary_score
        )

        return {
            'recency_score': recency_score,
            'frequency_score': frequency_score,
            'monetary_score': monetary_score,
            'rfm_total': rfm_total,
            'rfm_segment': segment,
            'days_since_last_purchase': days_ago if days_ago != 9999 else None,
        }

    @staticmethod
    def _get_rfm_segment(r: int, f: int, m: int) -> str:
        """RFM scores -> segment name।"""
        if r >= 4 and f >= 4 and m >= 4:
            return 'champion'
        elif r >= 4 and f >= 3:
            return 'loyal'
        elif r >= 3 and f >= 1 and m >= 3:
            return 'potential_loyal'
        elif r >= 4 and f == 1 and m == 1:
            return 'new'
        elif r >= 3 and f <= 2:
            return 'promising'
        elif r == 3 and f >= 3:
            return 'need_attention'
        elif r == 2 and f >= 2:
            return 'about_to_sleep'
        elif r <= 2 and f >= 3 and m >= 3:
            return 'at_risk'
        elif r == 1 and f >= 4 and m >= 4:
            return 'cant_lose'
        elif r == 2 and f <= 2:
            return 'hibernating'
        else:
            return 'lost'

    @staticmethod
    def update_ai_profile(customer, tenant=None):
        """
        Customer এর AI profile update করো।
        RFM + churn probability + engagement score।
        """
        from ..models.ai_personalization import CustomerAIProfile
        from ..models.core import Txn
        from ..models.points import LoyaltyPoints

        try:
            rfm = AIPersonalizationService.compute_rfm_score(customer, tenant)
            churn_prob = AIPersonalizationService.predict_churn_probability(customer)
            engagement = AIPersonalizationService.compute_engagement_score(customer)

            lp = customer.loyalty_points.first()
            avg_spend = Txn.objects.filter(customer=customer, value__gt=0).aggregate(
                avg=Avg('value')
            )['avg'] or Decimal('0')

            profile, _ = CustomerAIProfile.objects.update_or_create(
                customer=customer,
                defaults={
                    'tenant': tenant or customer.tenant,
                    'recency_score': rfm['recency_score'],
                    'frequency_score': rfm['frequency_score'],
                    'monetary_score': rfm['monetary_score'],
                    'rfm_total': rfm['rfm_total'],
                    'rfm_segment': rfm['rfm_segment'],
                    'churn_probability': churn_prob['probability'],
                    'churn_risk_level': churn_prob['risk_level'],
                    'days_since_last_purchase': rfm.get('days_since_last_purchase') or 0,
                    'avg_order_value': avg_spend,
                    'engagement_score': engagement,
                    'last_computed_at': timezone.now(),
                },
            )
            return profile
        except Exception as e:
            logger.error('AIPersonalizationService.update_ai_profile error for %s: %s', customer, e)
            return None

    @staticmethod
    def predict_churn_probability(customer) -> dict:
        """
        Simple rule-based churn prediction।
        Production এ ML model দিয়ে replace করুন।
        """
        from ..models.core import Txn
        now = timezone.now()

        # Rule-based signals
        signals = []
        score = Decimal('0')

        last_txn = Txn.objects.filter(customer=customer, value__gt=0).order_by('-timestamp').first()
        days_inactive = (now - last_txn.timestamp).days if last_txn else 999

        if days_inactive > 90:
            score += Decimal('0.30')
            signals.append('no_purchase_90d')
        elif days_inactive > 60:
            score += Decimal('0.20')
            signals.append('no_purchase_60d')
        elif days_inactive > 30:
            score += Decimal('0.10')
            signals.append('no_purchase_30d')

        # Frequency drop
        recent_count = Txn.objects.filter(
            customer=customer, value__gt=0,
            timestamp__gte=now - timedelta(days=30)
        ).count()
        older_count = Txn.objects.filter(
            customer=customer, value__gt=0,
            timestamp__range=(now - timedelta(days=90), now - timedelta(days=30))
        ).count()
        if older_count > 0 and recent_count == 0:
            score += Decimal('0.20')
            signals.append('purchase_frequency_dropped')
        if older_count > 3 and recent_count == 0:
            score += Decimal('0.15')
            signals.append('high_frequency_drop')

        # No redemption despite balance
        lp = customer.loyalty_points.first()
        if lp and lp.balance > 500:
            last_redemption = customer.redemption_requests.filter(
                created_at__gte=now - timedelta(days=60)
            ).first()
            if not last_redemption:
                score += Decimal('0.10')
                signals.append('high_balance_no_redemption')

        # Points expiring without action
        from ..models.points import PointsExpiry
        soon_expiring = PointsExpiry.objects.filter(
            customer=customer,
            expires_at__lte=now + timedelta(days=30),
            is_processed=False,
        ).exists()
        if soon_expiring and days_inactive > 20:
            score += Decimal('0.10')
            signals.append('points_expiring_inactive')

        score = min(score, Decimal('1.0'))

        risk_level = (
            'critical' if score >= Decimal('0.75') else
            'high' if score >= Decimal('0.50') else
            'medium' if score >= Decimal('0.25') else
            'low'
        )

        return {
            'probability': score,
            'risk_level': risk_level,
            'signals': signals,
        }

    @staticmethod
    def compute_engagement_score(customer) -> Decimal:
        """
        Overall engagement score (0-100)।
        """
        score = Decimal('0')

        try:
            # Recent purchase (max 25)
            from ..models.core import Txn
            recent = Txn.objects.filter(
                customer=customer, value__gt=0,
                timestamp__gte=timezone.now() - timedelta(days=30)
            ).count()
            score += min(Decimal(str(recent * 5)), Decimal('25'))

            # Streak (max 20)
            streak = customer.daily_streaks.filter(is_active=True).first()
            if streak:
                score += min(Decimal(str(streak.current_streak * 2)), Decimal('20'))

            # Badges (max 15)
            badge_count = customer.user_badges.count()
            score += min(Decimal(str(badge_count * 3)), Decimal('15'))

            # Redemptions (max 20)
            redemption_count = customer.redemption_requests.filter(
                status__in=['approved', 'fulfilled']
            ).count()
            score += min(Decimal(str(redemption_count * 4)), Decimal('20'))

            # Social actions (max 10)
            social_count = customer.social_actions.count()
            score += min(Decimal(str(social_count * 2)), Decimal('10'))

            # Referrals (max 10)
            referral_count = customer.referrals.count()
            score += min(Decimal(str(referral_count * 5)), Decimal('10'))

        except Exception as e:
            logger.debug('compute_engagement_score error: %s', e)

        return min(score, Decimal('100'))

    # ─── PERSONALIZED OFFERS ─────────────────────────────────────────

    @staticmethod
    def generate_win_back_offer(customer, tenant=None):
        """
        At-risk/churning customers এর জন্য win-back offer generate করো।
        """
        from ..models.ai_personalization import PersonalizedOffer
        from django.utils import timezone

        # Check if offer already active
        existing = PersonalizedOffer.objects.filter(
            customer=customer,
            trigger='win_back',
            status='active',
            valid_until__gte=timezone.now(),
        ).first()
        if existing:
            return existing

        churn = AIPersonalizationService.predict_churn_probability(customer)
        if churn['risk_level'] not in ['high', 'critical']:
            return None

        # Offer value based on customer value
        lp = customer.loyalty_points.first()
        if lp and lp.lifetime_earned > 5000:
            bonus_points = Decimal('500')
            multiplier = Decimal('2.0')
        elif lp and lp.lifetime_earned > 1000:
            bonus_points = Decimal('200')
            multiplier = Decimal('1.5')
        else:
            bonus_points = Decimal('100')
            multiplier = Decimal('1.5')

        offer = PersonalizedOffer.objects.create(
            customer=customer,
            tenant=tenant or customer.tenant,
            title=f'We miss you, {customer.firstname or customer.code}! 🎁',
            description=f'Come back and earn {bonus_points} bonus points + {multiplier}x multiplier!',
            offer_type='bonus_points',
            points_bonus=bonus_points,
            multiplier=multiplier,
            ai_generated=True,
            confidence_score=churn['probability'],
            reason=f'Churn risk: {churn["risk_level"]}. Signals: {", ".join(churn["signals"][:3])}',
            trigger='win_back',
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=14),
        )

        logger.info('AIPersonalizationService: win-back offer generated for %s', customer.code)
        return offer

    @staticmethod
    def generate_birthday_offer(customer, tenant=None):
        """Birthday personalized offer।"""
        from ..models.ai_personalization import PersonalizedOffer

        if not customer.date_of_birth:
            return None

        today = timezone.now().date()
        bday = customer.date_of_birth.replace(year=today.year)

        if not (bday - timedelta(days=3) <= today <= bday + timedelta(days=7)):
            return None

        existing = PersonalizedOffer.objects.filter(
            customer=customer,
            trigger='birthday',
            status='active',
            valid_until__gte=timezone.now(),
        ).first()
        if existing:
            return existing

        return PersonalizedOffer.objects.create(
            customer=customer,
            tenant=tenant or customer.tenant,
            title=f'🎂 Happy Birthday, {customer.firstname or customer.code}!',
            description='Enjoy 2x points on your birthday week + 500 bonus points!',
            offer_type='bonus_points',
            points_bonus=Decimal('500'),
            multiplier=Decimal('2.0'),
            ai_generated=True,
            confidence_score=Decimal('1.0'),
            reason='Birthday week offer',
            trigger='birthday',
            valid_from=timezone.now(),
            valid_until=timezone.now() + timedelta(days=7),
        )

    @staticmethod
    def get_recommendations_for_customer(customer, limit: int = 5, tenant=None) -> list:
        """
        Customer এর জন্য top N personalized recommendations।
        """
        from ..models.ai_personalization import AIRecommendation
        recommendations = []

        try:
            # 1. Tier upgrade nudge
            from ..utils import get_points_needed_for_next_tier, get_next_tier
            lp = customer.loyalty_points.first()
            lifetime = lp.lifetime_earned if lp else Decimal('0')
            ut = customer.current_tier
            tier_name = ut.tier.name if ut and ut.tier else 'bronze'
            next_tier = get_next_tier(tier_name)
            pts_needed = get_points_needed_for_next_tier(lifetime, tier_name) if next_tier else None

            if next_tier and pts_needed and pts_needed <= 500:
                recommendations.append({
                    'type': 'tier_upgrade',
                    'title': f'Only {int(pts_needed)} pts to {next_tier.title()}! 🚀',
                    'description': f'You are {int(pts_needed)} points away from {next_tier.title()} tier.',
                    'relevance_score': 0.95,
                    'urgency_score': 0.90,
                })

            # 2. Streak recommendation
            streak = customer.daily_streaks.filter(is_active=True).first()
            if not streak or streak.current_streak == 0:
                recommendations.append({
                    'type': 'streak',
                    'title': '🔥 Start your daily streak today!',
                    'description': 'Earn bonus points for consecutive daily activity.',
                    'relevance_score': 0.80,
                    'urgency_score': 0.70,
                })

            # 3. Pending offers
            from ..models.ai_personalization import PersonalizedOffer
            active_offers = PersonalizedOffer.objects.filter(
                customer=customer, status='active',
                valid_until__gte=timezone.now(),
            ).order_by('-confidence_score')[:2]

            for offer in active_offers:
                recommendations.append({
                    'type': 'reward',
                    'title': offer.title,
                    'description': offer.description,
                    'relevance_score': float(offer.confidence_score),
                    'urgency_score': 0.85,
                })

            # 4. Active campaigns
            from ..models.ai_personalization import LoyaltyCampaign
            campaigns = LoyaltyCampaign.active_campaigns.all()
            if tenant:
                campaigns = campaigns.filter(tenant=tenant)
            for campaign in campaigns[:1]:
                recommendations.append({
                    'type': 'campaign',
                    'title': f'🎉 {campaign.name} -- Join now!',
                    'description': campaign.description or 'Limited time campaign -- earn extra points!',
                    'relevance_score': 0.75,
                    'urgency_score': 0.80,
                })

        except Exception as e:
            logger.error('AIPersonalizationService.get_recommendations error: %s', e)

        return sorted(recommendations, key=lambda x: -x['relevance_score'])[:limit]

    @staticmethod
    def run_churn_scan(tenant=None, batch_size: int = 100) -> dict:
        """
        Bulk churn scan -- all at-risk customers কে identify করো।
        Celery task দিয়ে daily চালাও।
        """
        from ..models.core import Customer
        from ..models.ai_personalization import ChurnAlert

        customers = Customer.objects.filter(is_active=True)
        if tenant:
            customers = customers.filter(tenant=tenant)

        total_scanned = 0
        alerts_created = 0
        offers_generated = 0

        for customer in customers.iterator(chunk_size=batch_size):
            try:
                churn = AIPersonalizationService.predict_churn_probability(customer)

                if churn['risk_level'] in ['high', 'critical']:
                    alert, created = ChurnAlert.objects.get_or_create(
                        customer=customer,
                        is_resolved=False,
                        defaults={
                            'tenant': tenant or customer.tenant,
                            'risk_level': churn['risk_level'],
                            'churn_probability': churn['probability'],
                            'signals': churn['signals'],
                            'action_taken': 'none',
                        },
                    )
                    if created:
                        alerts_created += 1
                        # Auto-generate win-back offer
                        offer = AIPersonalizationService.generate_win_back_offer(customer, tenant)
                        if offer:
                            alert.offer = offer
                            alert.action_taken = 'offer_sent'
                            alert.save(update_fields=['offer', 'action_taken'])
                            offers_generated += 1

                total_scanned += 1
            except Exception as e:
                logger.error('churn_scan error for %s: %s', customer.id, e)

        logger.info(
            'AIPersonalizationService.run_churn_scan: scanned=%d, alerts=%d, offers=%d',
            total_scanned, alerts_created, offers_generated,
        )
        return {
            'total_scanned': total_scanned,
            'alerts_created': alerts_created,
            'offers_generated': offers_generated,
        }

    @staticmethod
    def compute_customer_profile(customer, tenant=None) -> dict:
        """Alias -- compute RFM + engagement + churn for a customer."""
        try:
            rfm = AIPersonalizationService.compute_rfm_score(customer, tenant=tenant)
            churn = AIPersonalizationService.predict_churn_probability(customer)
            engagement = float(AIPersonalizationService.compute_engagement_score(customer))
            return {
                'customer_id': customer.id,
                'rfm': rfm,
                'churn_probability': churn.get('churn_probability', 0),
                'churn_segment': churn.get('segment', 'low'),
                'engagement_score': engagement,
            }
        except Exception as e:
            logger.error('AIPersonalizationService.compute_customer_profile error: %s', e)
            return {'customer_id': getattr(customer, 'id', None), 'error': str(e)}

    @staticmethod
    def generate_recommendations(customer, limit: int = 5, tenant=None) -> list:
        """Alias for get_recommendations_for_customer."""
        return AIPersonalizationService.get_recommendations_for_customer(
            customer, limit=limit, tenant=tenant
        )

    @staticmethod
    def claim_offer(customer, offer_id: int, tenant=None) -> dict:
        """
        Customer claims a personalized AI offer.
        Marks offer as claimed, awards points if applicable.
        """
        try:
            from ..models.ai_personalization import PersonalizedOffer
            try:
                offer = PersonalizedOffer.objects.get(id=offer_id, customer=customer)
            except Exception:
                return {'success': False, 'error': 'Offer not found'}

            if getattr(offer, 'is_claimed', False):
                return {'success': False, 'error': 'Offer already claimed'}

            offer.is_claimed = True
            from django.utils import timezone
            offer.claimed_at = timezone.now()
            offer.save(update_fields=['is_claimed', 'claimed_at'])

            points_reward = getattr(offer, 'points_reward', 0) or 0
            if points_reward > 0:
                from .earn.BonusEventService import BonusEventService
                BonusEventService.award_bonus(
                    customer, points_reward,
                    reason=f'AI offer claimed: {offer.offer_type}',
                    triggered_by='ai_offer',
                    tenant=tenant,
                )

            return {
                'success': True,
                'offer_id': offer_id,
                'offer_type': offer.offer_type,
                'points_awarded': str(points_reward),
            }
        except Exception as e:
            logger.error('AIPersonalizationService.claim_offer error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def handle_churn_alert_action(customer, action: str = 'win_back',
                                   alert_id: int = None, tenant=None) -> dict:
        """
        Take action on a churn alert (win_back offer, special points, etc).
        action: 'win_back' | 'ignore' | 'discount_offer'
        """
        try:
            from django.utils import timezone
            result = {'customer_id': customer.id, 'action': action}

            if action == 'win_back':
                offer = AIPersonalizationService.generate_win_back_offer(customer, tenant=tenant)
                result['offer'] = offer

            elif action == 'discount_offer':
                offer = AIPersonalizationService.generate_birthday_offer(customer, tenant=tenant)
                result['offer'] = offer

            elif action == 'ignore':
                result['message'] = 'Alert acknowledged, no action taken'

            # Mark alert as actioned
            if alert_id:
                try:
                    from ..models.ai_personalization import ChurnAlert
                    ChurnAlert.objects.filter(id=alert_id, customer=customer).update(
                        status='actioned',
                        actioned_at=timezone.now(),
                        action_taken=action,
                    )
                except Exception:
                    pass

            logger.info('AIPersonalizationService.handle_churn_alert_action: %s -> %s',
                        customer.code, action)
            return {'success': True, **result}
        except Exception as e:
            logger.error('AIPersonalizationService.handle_churn_alert_action error: %s', e)
            return {'success': False, 'error': str(e)}
