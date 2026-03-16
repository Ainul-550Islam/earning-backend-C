from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from ..models import AdNetworkWebhookLog, AdNetwork
from ..services.AdNetworkFactory import AdNetworkFactory
import json
import logging

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AdMobWebhookView(View):
    
    def post(self, request):
        """Handle AdMob conversion postback"""
        try:
            # Parse payload
            payload = json.loads(request.body) if request.body else request.GET.dict()
            
            # Get AdMob network
            ad_network = AdNetwork.objects.get(network_type='admob')
            
            # Log webhook
            webhook_log = AdNetworkWebhookLog.objects.create(
                ad_network=ad_network,
                payload=payload,
                headers=dict(request.headers),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Get service and verify
            service = AdNetworkFactory.get_service('admob')
            
            if not service.verify_postback(request):
                webhook_log.processing_error = 'Invalid signature'
                webhook_log.save()
                return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=403)
            
            # Process conversion
            success, engagement = service.process_conversion(payload)
            
            if success:
                webhook_log.processed = True
                webhook_log.engagement = engagement
                webhook_log.save()
                
                return JsonResponse({'status': 'success'})
            else:
                webhook_log.processing_error = 'Engagement not found'
                webhook_log.save()
                return JsonResponse({'status': 'error', 'message': 'Engagement not found'}, status=404)
        
        except Exception as e:
            logger.error(f"AdMob webhook error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class UnityAdsWebhookView(View):
    
    def post(self, request):
        """Handle Unity Ads conversion postback"""
        try:
            payload = json.loads(request.body) if request.body else request.GET.dict()
            
            ad_network = AdNetwork.objects.get(network_type='unity')
            
            webhook_log = AdNetworkWebhookLog.objects.create(
                ad_network=ad_network,
                payload=payload,
                headers=dict(request.headers),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            service = AdNetworkFactory.get_service('unity')
            success, engagement = service.process_conversion(payload)
            
            if success:
                webhook_log.processed = True
                webhook_log.engagement = engagement
                webhook_log.save()
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error'}, status=404)
        
        except Exception as e:
            logger.error(f"Unity Ads webhook error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class IronSourceWebhookView(View):
    
    def post(self, request):
        """Handle IronSource conversion postback"""
        # Similar implementation
        return JsonResponse({'status': 'success'})
        try:
            payload = json.loads(request.body) if request.body else request.GET.dict()
            
            ad_network = AdNetwork.objects.get(network_type='ironsource')
            
            webhook_log = AdNetworkWebhookLog.objects.create(
                ad_network=ad_network,
                payload=payload,
                headers=dict(request.headers),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            service = AdNetworkFactory.get_service('ironsource')
            success, engagement = service.process_conversion(payload)
            
            if success:
                webhook_log.processed = True
                webhook_log.engagement = engagement
                webhook_log.save()
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error'}, status=404)
        
        except Exception as e:
            logger.error(f"IronSource webhook error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
