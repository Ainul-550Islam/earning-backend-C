# api/referral/viewsets/ReferralCampaignViewSet.py
# Campaign: list, detail, admin create/update
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class ReferralCampaignViewSet(APIView):
    """
    GET  /api/referral/campaigns/         — active campaigns (public)
    POST /api/referral/campaigns/         — create campaign (admin)
    """
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get(self, request):
        from api.referral.services.ReferralCampaignService import ReferralCampaignService
        campaigns = ReferralCampaignService.get_all_active_campaigns()
        return Response({'success': True, 'campaigns': campaigns})

    def post(self, request):
        from api.referral.models import ReferralCampaign
        from django.utils.text import slugify

        data = request.data
        required = ['name', 'start_date', 'end_date']
        for field in required:
            if not data.get(field):
                return Response(
                    {'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        campaign = ReferralCampaign.objects.create(
            name=data['name'],
            slug=slugify(data['name']),
            description=data.get('description', ''),
            start_date=data['start_date'],
            end_date=data['end_date'],
            bonus_multiplier=data.get('bonus_multiplier', 1),
            extra_signup_bonus=data.get('extra_signup_bonus', 0),
            max_budget=data.get('max_budget'),
            max_referrals=data.get('max_referrals'),
            is_active=data.get('is_active', True),
            is_featured=data.get('is_featured', False),
            terms=data.get('terms', ''),
            created_by=request.user,
        )

        return Response({
            'success': True,
            'campaign_id': campaign.id,
            'name': campaign.name,
        }, status=status.HTTP_201_CREATED)


class CampaignDetailView(APIView):
    """
    GET    /api/referral/campaigns/<id>/            — campaign detail
    PATCH  /api/referral/campaigns/<id>/            — update (admin)
    DELETE /api/referral/campaigns/<id>/end/        — end campaign (admin)
    POST   /api/referral/campaigns/<id>/activate/  — activate (admin)
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get(self, request, campaign_id):
        from api.referral.services.ReferralCampaignService import ReferralCampaignService
        data = ReferralCampaignService.get_campaign_performance(campaign_id)
        if 'error' in data:
            return Response(data, status=404)
        return Response({'success': True, **data})

    def patch(self, request, campaign_id):
        from api.referral.models import ReferralCampaign
        from api.referral.services.ReferralCampaignService import ReferralCampaignService

        try:
            campaign = ReferralCampaign.objects.get(id=campaign_id)
        except ReferralCampaign.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        updatable = [
            'name', 'description', 'bonus_multiplier', 'extra_signup_bonus',
            'max_budget', 'max_referrals', 'is_active', 'is_featured',
            'terms', 'end_date',
        ]
        for field in updatable:
            if field in request.data:
                setattr(campaign, field, request.data[field])
        campaign.save()
        ReferralCampaignService.invalidate_campaign_cache()

        return Response({'success': True})

    def delete(self, request, campaign_id):
        from api.referral.services.ReferralCampaignService import ReferralCampaignService
        result = ReferralCampaignService.end_campaign(campaign_id)
        return Response(result)


class CampaignActivateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, campaign_id):
        from api.referral.services.ReferralCampaignService import ReferralCampaignService
        result = ReferralCampaignService.start_campaign(campaign_id)
        return Response(result)