# api/referral/viewsets/ReferralSettingsViewSet.py
# Admin: referral settings CRUD
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class ReferralSettingsViewSet(APIView):
    """
    GET  /api/referral/settings/v2/      — get current settings
    POST /api/referral/settings/v2/      — update settings
    POST /api/referral/settings/v2/reset/ — reset to defaults
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import ReferralSettings

        settings = ReferralSettings.objects.select_related(
            'active_campaign'
        ).first()
        if not settings:
            settings = ReferralSettings.objects.create()

        return Response({
            'id': settings.id,
            'direct_signup_bonus': float(settings.direct_signup_bonus),
            'referrer_signup_bonus': float(settings.referrer_signup_bonus),
            'level1_commission_rate': float(settings.level1_commission_rate),
            'level2_commission_rate': float(settings.level2_commission_rate),
            'level3_commission_rate': float(settings.level3_commission_rate),
            'commission_hold_days': settings.commission_hold_days,
            'max_referral_depth': settings.max_referral_depth,
            'min_payout_threshold': float(settings.min_payout_threshold),
            'referral_cookie_days': settings.referral_cookie_days,
            'allow_self_referral': settings.allow_self_referral,
            'team_bonus_enabled': settings.team_bonus_enabled,
            'team_bonus_min_referrals': settings.team_bonus_min_referrals,
            'team_bonus_rate': float(settings.team_bonus_rate or 0),
            'is_active': settings.is_active,
            'active_campaign': (
                {
                    'id': settings.active_campaign.id,
                    'name': settings.active_campaign.name,
                }
                if settings.active_campaign_id else None
            ),
        })

    def post(self, request):
        from api.referral.models import ReferralSettings

        settings = ReferralSettings.objects.first()
        if not settings:
            settings = ReferralSettings.objects.create()

        updatable_fields = [
            'direct_signup_bonus', 'referrer_signup_bonus',
            'level1_commission_rate', 'level2_commission_rate',
            'level3_commission_rate', 'commission_hold_days',
            'max_referral_depth', 'min_payout_threshold',
            'referral_cookie_days', 'allow_self_referral',
            'team_bonus_enabled', 'team_bonus_min_referrals',
            'team_bonus_rate', 'is_active',
        ]

        for field in updatable_fields:
            if field in request.data:
                setattr(settings, field, request.data[field])

        # Active campaign update
        if 'active_campaign_id' in request.data:
            from api.referral.models import ReferralCampaign
            campaign_id = request.data['active_campaign_id']
            if campaign_id:
                try:
                    settings.active_campaign = ReferralCampaign.objects.get(
                        id=campaign_id
                    )
                except ReferralCampaign.DoesNotExist:
                    return Response(
                        {'error': 'Campaign not found'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                settings.active_campaign = None

        settings.save()
        cache.delete('referral_settings')

        logger.info(f"Settings updated by {request.user.username}")
        return Response({'success': True, 'message': 'Settings updated'})