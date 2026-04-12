# =============================================================================
# promotions/tracker_integration/voluum.py
# Voluum Tracker Integration — most popular affiliate tracker
# Publishers use Voluum to track their campaigns across networks
# =============================================================================
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings


class VoluumIntegration:
    """Generate Voluum-compatible tracking URLs and postbacks."""

    def get_tracking_url_template(self, campaign_id: int, publisher_id: int) -> dict:
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return {
            'campaign_id': campaign_id,
            'tracking_url': f'{base}/api/promotions/go/{campaign_id}/?pub={publisher_id}&clickid={{clickid}}&s1={{s1}}&s2={{s2}}&s3={{s3}}',
            'postback_url': f'{base}/api/promotions/postback/?clickid={{clickid}}&payout={{payout}}&status=approved',
            'voluum_setup': {
                'step1': 'In Voluum: Affiliate Networks → Add New → Custom',
                'step2': f'Tracking URL: {base}/api/promotions/go/{campaign_id}/?pub={publisher_id}&clickid={{clickid}}',
                'step3': f'Postback URL: {base}/api/promotions/postback/?clickid={{clickid}}&payout={{payout}}',
                'step4': 'Click ID Parameter: clickid',
                'step5': 'Test with a click, verify in conversion log',
            }
        }

    def get_supported_trackers(self) -> list:
        return [
            {'name': 'Voluum', 'clickid_param': 'clickid', 'status': 'supported'},
            {'name': 'BeMob', 'clickid_param': 'click_id', 'status': 'supported'},
            {'name': 'Binom', 'clickid_param': 't', 'status': 'supported'},
            {'name': 'CPVLab / CPVOne', 'clickid_param': 'click_id', 'status': 'supported'},
            {'name': 'RedTrack', 'clickid_param': 'clickid', 'status': 'supported'},
            {'name': 'Hyros', 'clickid_param': 'hyros_aid', 'status': 'supported'},
            {'name': 'Funnel Flux', 'clickid_param': 'tid', 'status': 'supported'},
            {'name': 'ThriveTracker', 'clickid_param': 'click_id', 'status': 'supported'},
        ]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracker_setup_view(request, campaign_id):
    integration = VoluumIntegration()
    return Response(integration.get_tracking_url_template(campaign_id, request.user.id))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supported_trackers_view(request):
    integration = VoluumIntegration()
    return Response({'trackers': integration.get_supported_trackers()})
