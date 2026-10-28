# api/djoyalty/serializers/AIPersonalizationSerializer.py
"""
Djoyalty AI & Personalization Serializers -- NEW।
CustomerAIProfile, PersonalizedOffer, AIRecommendation, ChurnAlert --
all had ZERO serializers despite being 55KB+ of built logic।
"""
from rest_framework import serializers
from ..models.ai_personalization import (
    CustomerAIProfile, PersonalizedOffer,
    AIRecommendation, ChurnAlert,
)


# ─── Customer AI Profile ───────────────────────────────────────────────────────

class CustomerAIProfileSerializer(serializers.ModelSerializer):
    """
    Full AI profile -- shows RFM scores, churn risk, CLV।
    Admin-level read: shows all scores।
    """
    customer_code  = serializers.SerializerMethodField()
    rfm_label      = serializers.SerializerMethodField()
    churn_label    = serializers.SerializerMethodField()
    clv_summary    = serializers.SerializerMethodField()

    class Meta:
        model = CustomerAIProfile
        fields = [
            'id', 'customer', 'customer_code',
            # RFM
            'recency_score', 'frequency_score', 'monetary_score',
            'rfm_total', 'rfm_segment', 'rfm_label',
            # Churn
            'churn_probability', 'churn_risk_level', 'churn_label',
            'days_since_last_purchase', 'days_since_last_login',
            # CLV
            'predicted_clv_30d', 'predicted_clv_90d', 'predicted_clv_1y',
            'actual_clv', 'clv_summary',
            # Behavioral
            'preferred_category', 'preferred_channel',
            'avg_order_value', 'purchase_frequency_days',
            'best_day_of_week', 'best_hour_of_day',
            # Engagement
            'engagement_score',
            # Meta
            'last_computed_at', 'model_version',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_rfm_label(self, obj) -> str:
        labels = {
            'champion':        '🏆 Champion',
            'loyal':           '💎 Loyal Customer',
            'potential_loyal': '🌟 Potential Loyalist',
            'new':             '🆕 New Customer',
            'promising':       '✨ Promising',
            'need_attention':  '⚠️ Need Attention',
            'about_to_sleep':  '😴 About to Sleep',
            'at_risk':         '🔴 At Risk',
            'cant_lose':       '🆘 Can\'t Lose Them',
            'hibernating':     '❄️ Hibernating',
            'lost':            '💀 Lost',
        }
        return labels.get(obj.rfm_segment, obj.rfm_segment)

    def get_churn_label(self, obj) -> str:
        p = float(obj.churn_probability)
        if p < 0.2:
            return '🟢 Low Risk'
        elif p < 0.5:
            return '🟡 Medium Risk'
        elif p < 0.75:
            return '🔴 High Risk'
        return '🚨 Critical'

    def get_clv_summary(self, obj) -> dict:
        return {
            '30d':  str(obj.predicted_clv_30d),
            '90d':  str(obj.predicted_clv_90d),
            '1y':   str(obj.predicted_clv_1y),
            'actual': str(obj.actual_clv),
        }


class CustomerAIProfileSummarySerializer(serializers.ModelSerializer):
    """Lightweight -- for customer-facing: only engagement + churn risk label."""
    churn_label = serializers.SerializerMethodField()

    class Meta:
        model = CustomerAIProfile
        fields = [
            'rfm_segment', 'churn_risk_level', 'churn_label',
            'engagement_score', 'last_computed_at',
        ]
        read_only_fields = fields

    def get_churn_label(self, obj) -> str:
        labels = {
            'low': '🟢 Low Risk', 'medium': '🟡 Medium Risk',
            'high': '🔴 High Risk', 'critical': '🚨 Critical',
        }
        return labels.get(obj.churn_risk_level, obj.churn_risk_level)


# ─── Personalized Offer ────────────────────────────────────────────────────────

class PersonalizedOfferSerializer(serializers.ModelSerializer):
    """
    AI-generated offer shown to customer।
    """
    customer_code   = serializers.SerializerMethodField()
    is_valid        = serializers.SerializerMethodField()
    days_remaining  = serializers.SerializerMethodField()
    offer_summary   = serializers.SerializerMethodField()

    class Meta:
        model = PersonalizedOffer
        fields = [
            'id', 'customer', 'customer_code',
            'title', 'description', 'offer_type',
            'points_bonus', 'multiplier', 'discount_percent',
            'ai_generated', 'confidence_score', 'reason', 'trigger',
            'valid_from', 'valid_until',
            'status', 'viewed_at', 'claimed_at', 'dismissed_at',
            'campaign',
            'is_valid', 'days_remaining', 'offer_summary',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'customer_code', 'ai_generated', 'confidence_score',
            'reason', 'viewed_at', 'claimed_at', 'dismissed_at',
            'is_valid', 'days_remaining', 'offer_summary',
            'created_at', 'updated_at',
        ]

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_is_valid(self, obj) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if obj.status != 'active':
            return False
        if obj.valid_until and obj.valid_until < now:
            return False
        return True

    def get_days_remaining(self, obj) -> int:
        from django.utils import timezone
        if obj.valid_until:
            delta = obj.valid_until.date() - timezone.now().date()
            return max(delta.days, 0)
        return 0

    def get_offer_summary(self, obj) -> str:
        """Human-readable one-liner for push notification."""
        if obj.offer_type == 'bonus_points':
            return f'Earn {obj.points_bonus} bonus points!'
        elif obj.offer_type == 'points_multiplier':
            return f'{obj.multiplier}× points on your next purchase!'
        elif obj.offer_type == 'discount':
            return f'{obj.discount_percent}% off your next order!'
        elif obj.offer_type == 'win_back':
            return 'We miss you! Special offer just for you.'
        elif obj.offer_type == 'birthday':
            return '🎂 Happy Birthday! Claim your birthday gift.'
        return obj.title


class PersonalizedOfferClaimSerializer(serializers.Serializer):
    """POST /ai/offers/{id}/claim/"""
    reference = serializers.CharField(required=False, allow_blank=True)


class PersonalizedOfferDismissSerializer(serializers.Serializer):
    """POST /ai/offers/{id}/dismiss/ -- customer dismisses offer."""
    reason = serializers.ChoiceField(
        choices=['not_interested', 'already_used', 'too_expensive', 'other'],
        required=False, default='other',
    )


# ─── AI Recommendation ────────────────────────────────────────────────────────

class AIRecommendationSerializer(serializers.ModelSerializer):
    """
    AI-generated recommendation card for customer dashboard।
    """
    customer_code   = serializers.SerializerMethodField()
    is_valid        = serializers.SerializerMethodField()

    class Meta:
        model = AIRecommendation
        fields = [
            'id', 'customer', 'customer_code',
            'recommendation_type', 'title', 'description', 'action_url',
            'linked_campaign_id', 'linked_challenge_id', 'linked_voucher_id',
            'relevance_score', 'urgency_score',
            'position', 'is_shown', 'is_clicked',
            'shown_at', 'clicked_at', 'expires_at',
            'is_valid',
            'created_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_is_valid(self, obj) -> bool:
        from django.utils import timezone
        if obj.expires_at and obj.expires_at < timezone.now():
            return False
        return True


class AIRecommendationClickSerializer(serializers.Serializer):
    """POST /ai/recommendations/{id}/click/ -- track click."""
    pass  # no body needed -- just marks clicked_at


# ─── Churn Alert ──────────────────────────────────────────────────────────────

class ChurnAlertSerializer(serializers.ModelSerializer):
    """
    Churn alert -- admin dashboard: who is about to leave।
    """
    customer_code   = serializers.SerializerMethodField()
    days_since      = serializers.SerializerMethodField()
    risk_badge      = serializers.SerializerMethodField()

    class Meta:
        model = ChurnAlert
        fields = [
            'id', 'customer', 'customer_code',
            'risk_level', 'risk_badge', 'churn_probability',
            'predicted_churn_date', 'signals',
            'action_taken', 'offer',
            'detected_at', 'resolved_at', 'is_resolved',
            'days_since',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'risk_badge', 'days_since', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_days_since(self, obj) -> int:
        from django.utils import timezone
        delta = timezone.now() - obj.detected_at
        return delta.days

    def get_risk_badge(self, obj) -> str:
        badges = {
            'medium':   '🟡 Medium',
            'high':     '🔴 High',
            'critical': '🚨 Critical',
        }
        return badges.get(obj.risk_level, obj.risk_level)


class ChurnAlertActionSerializer(serializers.Serializer):
    """POST /ai/churn-alerts/{id}/action/ -- admin takes action."""
    action = serializers.ChoiceField(choices=[
        'send_offer', 'send_notification', 'manual_review', 'mark_resolved',
    ])
    note   = serializers.CharField(required=False, allow_blank=True)
