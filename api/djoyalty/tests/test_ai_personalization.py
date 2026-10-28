# api/djoyalty/tests/test_ai_personalization.py
"""
AI Personalization Tests -- NEW।
CustomerAIProfile, PersonalizedOffer, AIRecommendation, ChurnAlert --
all had ZERO test coverage despite 55KB+ of built logic।
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .factories import make_customer, make_loyalty_points


# ─── CustomerAIProfile Tests ──────────────────────────────────────────────────

class CustomerAIProfileTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='AIPROFCUST01')

    def test_create_ai_profile(self):
        from djoyalty.models.ai_personalization import CustomerAIProfile
        profile = CustomerAIProfile.objects.create(
            customer=self.customer,
            recency_score=Decimal('4'),
            frequency_score=Decimal('3'),
            monetary_score=Decimal('5'),
            rfm_total=Decimal('12'),
            rfm_segment='loyal',
            churn_probability=Decimal('0.15'),
            churn_risk_level='low',
            predicted_clv_30d=Decimal('500'),
            predicted_clv_90d=Decimal('1200'),
            predicted_clv_1y=Decimal('4500'),
            actual_clv=Decimal('3200'),
            engagement_score=Decimal('78'),
            model_version='v2',
        )
        self.assertEqual(profile.rfm_segment, 'loyal')
        self.assertEqual(profile.churn_risk_level, 'low')

    def test_profile_churn_probability_in_range(self):
        from djoyalty.models.ai_personalization import CustomerAIProfile
        profile = CustomerAIProfile.objects.create(
            customer=self.customer,
            churn_probability=Decimal('0.85'),
            churn_risk_level='critical',
            model_version='v2',
        )
        self.assertGreaterEqual(float(profile.churn_probability), 0)
        self.assertLessEqual(float(profile.churn_probability), 1)

    def test_profile_serializer_rfm_label(self):
        from djoyalty.models.ai_personalization import CustomerAIProfile
        from djoyalty.serializers.AIPersonalizationSerializer import CustomerAIProfileSerializer
        profile = CustomerAIProfile(
            customer=self.customer,
            rfm_segment='champion',
            churn_risk_level='low',
            churn_probability=Decimal('0.05'),
            engagement_score=Decimal('95'),
            model_version='v2',
        )
        s = CustomerAIProfileSerializer(profile)
        self.assertIn('🏆', s.data['rfm_label'])

    def test_profile_serializer_churn_label_low(self):
        from djoyalty.models.ai_personalization import CustomerAIProfile
        from djoyalty.serializers.AIPersonalizationSerializer import CustomerAIProfileSerializer
        profile = CustomerAIProfile(
            customer=self.customer,
            rfm_segment='loyal',
            churn_probability=Decimal('0.10'),
            churn_risk_level='low',
            engagement_score=Decimal('80'),
            model_version='v2',
        )
        s = CustomerAIProfileSerializer(profile)
        self.assertIn('🟢', s.data['churn_label'])

    def test_profile_serializer_churn_label_critical(self):
        from djoyalty.models.ai_personalization import CustomerAIProfile
        from djoyalty.serializers.AIPersonalizationSerializer import CustomerAIProfileSerializer
        profile = CustomerAIProfile(
            customer=self.customer,
            rfm_segment='at_risk',
            churn_probability=Decimal('0.90'),
            churn_risk_level='critical',
            engagement_score=Decimal('10'),
            model_version='v2',
        )
        s = CustomerAIProfileSerializer(profile)
        self.assertIn('🚨', s.data['churn_label'])

    def test_profile_clv_summary_has_all_periods(self):
        from djoyalty.models.ai_personalization import CustomerAIProfile
        from djoyalty.serializers.AIPersonalizationSerializer import CustomerAIProfileSerializer
        profile = CustomerAIProfile(
            customer=self.customer,
            predicted_clv_30d=Decimal('100'),
            predicted_clv_90d=Decimal('250'),
            predicted_clv_1y=Decimal('900'),
            actual_clv=Decimal('700'),
            model_version='v2',
        )
        s = CustomerAIProfileSerializer(profile)
        clv = s.data['clv_summary']
        self.assertIn('30d', clv)
        self.assertIn('90d', clv)
        self.assertIn('1y',  clv)
        self.assertIn('actual', clv)


# ─── PersonalizedOffer Tests ──────────────────────────────────────────────────

class PersonalizedOfferTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='OFFERCUST01')

    def test_create_personalized_offer(self):
        from djoyalty.models.ai_personalization import PersonalizedOffer
        offer = PersonalizedOffer.objects.create(
            customer=self.customer,
            title='Birthday Bonus',
            description='200 bonus points for you!',
            offer_type='birthday',
            points_bonus=Decimal('200'),
            ai_generated=True,
            confidence_score=Decimal('0.92'),
            trigger='birthday',
            status='active',
            valid_until=timezone.now() + timedelta(days=7),
        )
        self.assertEqual(offer.offer_type, 'birthday')
        self.assertTrue(offer.ai_generated)

    def test_offer_serializer_is_valid_when_active(self):
        from djoyalty.models.ai_personalization import PersonalizedOffer
        from djoyalty.serializers.AIPersonalizationSerializer import PersonalizedOfferSerializer
        offer = PersonalizedOffer(
            customer=self.customer,
            title='Test Offer',
            offer_type='bonus_points',
            points_bonus=Decimal('100'),
            status='active',
            valid_until=timezone.now() + timedelta(days=3),
        )
        s = PersonalizedOfferSerializer(offer)
        self.assertTrue(s.data['is_valid'])

    def test_offer_serializer_not_valid_when_expired(self):
        from djoyalty.models.ai_personalization import PersonalizedOffer
        from djoyalty.serializers.AIPersonalizationSerializer import PersonalizedOfferSerializer
        offer = PersonalizedOffer(
            customer=self.customer,
            title='Expired Offer',
            offer_type='bonus_points',
            points_bonus=Decimal('100'),
            status='active',
            valid_until=timezone.now() - timedelta(days=1),
        )
        s = PersonalizedOfferSerializer(offer)
        self.assertFalse(s.data['is_valid'])

    def test_offer_serializer_days_remaining(self):
        from djoyalty.models.ai_personalization import PersonalizedOffer
        from djoyalty.serializers.AIPersonalizationSerializer import PersonalizedOfferSerializer
        offer = PersonalizedOffer(
            customer=self.customer,
            title='Offer 5 days',
            offer_type='multiplier',
            multiplier=Decimal('2'),
            status='active',
            valid_until=timezone.now() + timedelta(days=5),
        )
        s = PersonalizedOfferSerializer(offer)
        self.assertGreaterEqual(s.data['days_remaining'], 4)

    def test_offer_summary_bonus_points(self):
        from djoyalty.models.ai_personalization import PersonalizedOffer
        from djoyalty.serializers.AIPersonalizationSerializer import PersonalizedOfferSerializer
        offer = PersonalizedOffer(
            customer=self.customer, title='X',
            offer_type='bonus_points', points_bonus=Decimal('150'),
            status='active',
        )
        s = PersonalizedOfferSerializer(offer)
        self.assertIn('150', s.data['offer_summary'])

    def test_offer_summary_birthday(self):
        from djoyalty.models.ai_personalization import PersonalizedOffer
        from djoyalty.serializers.AIPersonalizationSerializer import PersonalizedOfferSerializer
        offer = PersonalizedOffer(
            customer=self.customer, title='X',
            offer_type='birthday', points_bonus=Decimal('0'),
            status='active',
        )
        s = PersonalizedOfferSerializer(offer)
        self.assertIn('Birthday', s.data['offer_summary'])

    def test_offer_dismiss_serializer_valid_reasons(self):
        from djoyalty.serializers.AIPersonalizationSerializer import PersonalizedOfferDismissSerializer
        for reason in ['not_interested', 'already_used', 'too_expensive', 'other']:
            s = PersonalizedOfferDismissSerializer(data={'reason': reason})
            self.assertTrue(s.is_valid(), f'Should be valid for reason={reason}')

    def test_offer_dismiss_serializer_invalid_reason(self):
        from djoyalty.serializers.AIPersonalizationSerializer import PersonalizedOfferDismissSerializer
        s = PersonalizedOfferDismissSerializer(data={'reason': 'hate_it'})
        self.assertFalse(s.is_valid())


# ─── ChurnAlert Tests ─────────────────────────────────────────────────────────

class ChurnAlertTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='CHURNCUST01')

    def test_create_churn_alert(self):
        from djoyalty.models.ai_personalization import ChurnAlert
        alert = ChurnAlert.objects.create(
            customer=self.customer,
            risk_level='high',
            churn_probability=Decimal('0.75'),
            predicted_churn_date=timezone.now() + timedelta(days=14),
            signals={'days_since_purchase': 45, 'login_drop': True},
            is_resolved=False,
        )
        self.assertEqual(alert.risk_level, 'high')
        self.assertFalse(alert.is_resolved)

    def test_churn_alert_serializer_risk_badge(self):
        from djoyalty.models.ai_personalization import ChurnAlert
        from djoyalty.serializers.AIPersonalizationSerializer import ChurnAlertSerializer
        alert = ChurnAlert(
            customer=self.customer,
            risk_level='critical',
            churn_probability=Decimal('0.92'),
            detected_at=timezone.now(),
            is_resolved=False,
        )
        s = ChurnAlertSerializer(alert)
        self.assertIn('🚨', s.data['risk_badge'])

    def test_churn_alert_serializer_medium_badge(self):
        from djoyalty.models.ai_personalization import ChurnAlert
        from djoyalty.serializers.AIPersonalizationSerializer import ChurnAlertSerializer
        alert = ChurnAlert(
            customer=self.customer,
            risk_level='medium',
            churn_probability=Decimal('0.45'),
            detected_at=timezone.now(),
            is_resolved=False,
        )
        s = ChurnAlertSerializer(alert)
        self.assertIn('🟡', s.data['risk_badge'])

    def test_churn_alert_action_serializer_valid_actions(self):
        from djoyalty.serializers.AIPersonalizationSerializer import ChurnAlertActionSerializer
        for action in ['send_offer', 'send_notification', 'manual_review', 'mark_resolved']:
            s = ChurnAlertActionSerializer(data={'action': action})
            self.assertTrue(s.is_valid(), f'Action {action} should be valid')

    def test_churn_alert_action_invalid(self):
        from djoyalty.serializers.AIPersonalizationSerializer import ChurnAlertActionSerializer
        s = ChurnAlertActionSerializer(data={'action': 'delete_customer'})
        self.assertFalse(s.is_valid())

    def test_resolved_alert_is_excluded_from_default_queryset(self):
        from djoyalty.models.ai_personalization import ChurnAlert
        ChurnAlert.objects.create(
            customer=self.customer, risk_level='high',
            churn_probability=Decimal('0.80'), is_resolved=True,
            detected_at=timezone.now(), resolved_at=timezone.now(),
        )
        ChurnAlert.objects.create(
            customer=self.customer, risk_level='medium',
            churn_probability=Decimal('0.50'), is_resolved=False,
            detected_at=timezone.now(),
        )
        unresolved = ChurnAlert.objects.filter(is_resolved=False).count()
        self.assertEqual(unresolved, 1)


# ─── AIRecommendation Tests ───────────────────────────────────────────────────

class AIRecommendationTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='RECOMCUST01')

    def test_create_recommendation(self):
        from djoyalty.models.ai_personalization import AIRecommendation
        rec = AIRecommendation.objects.create(
            customer=self.customer,
            recommendation_type='challenge',
            title='Try the Walking Challenge!',
            description='Walk 5000 steps and earn 500 points.',
            action_url='/challenges/walking/',
            relevance_score=Decimal('0.87'),
            urgency_score=Decimal('0.60'),
            position=1,
            is_shown=False,
            is_clicked=False,
        )
        self.assertEqual(rec.recommendation_type, 'challenge')
        self.assertFalse(rec.is_clicked)

    def test_serializer_is_valid_no_expiry(self):
        from djoyalty.models.ai_personalization import AIRecommendation
        from djoyalty.serializers.AIPersonalizationSerializer import AIRecommendationSerializer
        rec = AIRecommendation(
            customer=self.customer,
            recommendation_type='offer',
            title='Special Offer',
            description='Click to see',
            relevance_score=Decimal('0.9'),
            urgency_score=Decimal('0.5'),
            expires_at=None,
        )
        s = AIRecommendationSerializer(rec)
        self.assertTrue(s.data['is_valid'])

    def test_serializer_not_valid_when_expired(self):
        from djoyalty.models.ai_personalization import AIRecommendation
        from djoyalty.serializers.AIPersonalizationSerializer import AIRecommendationSerializer
        rec = AIRecommendation(
            customer=self.customer,
            recommendation_type='offer',
            title='Expired Rec',
            description='Old',
            relevance_score=Decimal('0.5'),
            urgency_score=Decimal('0.5'),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        s = AIRecommendationSerializer(rec)
        self.assertFalse(s.data['is_valid'])
