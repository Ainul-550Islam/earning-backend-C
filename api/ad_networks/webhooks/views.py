from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from ..models import AdNetworkWebhookLog, AdNetwork
from ..services.AdNetworkFactory import AdNetworkFactory
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# BASE WEBHOOK VIEW
# ============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class BaseWebhookView(View):
    """Base webhook view for all ad networks"""
    
    network_type = None
    
    def post(self, request):
        """Handle webhook postback"""
        try:
            if not self.network_type:
                return JsonResponse({'status': 'error', 'message': 'Network type not specified'}, status=400)
            
            # Parse payload
            payload = json.loads(request.body) if request.body else request.GET.dict()
            
            # Get network
            try:
                ad_network = AdNetwork.objects.get(network_type=self.network_type)
            except AdNetwork.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': f'Network {self.network_type} not found'}, status=404)
            
            # Log webhook
            webhook_log = AdNetworkWebhookLog.objects.create(
                ad_network=ad_network,
                payload=payload,
                headers=dict(request.headers),
                ip_address=request.META.get('REMOTE_ADDR'),
                tenant_id=getattr(ad_network, 'tenant_id', 'default')
            )
            
            # Get service and verify
            try:
                service = AdNetworkFactory.get_service(self.network_type)
            except Exception as e:
                webhook_log.processing_error = f'Service not available: {str(e)}'
                webhook_log.save()
                return JsonResponse({'status': 'error', 'message': 'Service not available'}, status=503)
            
            # Verify postback if service supports it
            if hasattr(service, 'verify_postback'):
                if not service.verify_postback(request):
                    webhook_log.processing_error = 'Invalid signature'
                    webhook_log.save()
                    return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=403)
            
            # Process conversion
            try:
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
                webhook_log.processing_error = f'Processing error: {str(e)}'
                webhook_log.save()
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        
        except Exception as e:
            logger.error(f"{self.network_type} webhook error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================================================
# BASIC NETWORKS (1-6)
# ============================================================================

class AdMobWebhookView(BaseWebhookView):
    network_type = 'admob'


class UnityAdsWebhookView(BaseWebhookView):
    network_type = 'unity'


class IronSourceWebhookView(BaseWebhookView):
    network_type = 'ironsource'


class AppLovinWebhookView(BaseWebhookView):
    network_type = 'applovin'


class TapjoyWebhookView(BaseWebhookView):
    network_type = 'tapjoy'


class VungleWebhookView(BaseWebhookView):
    network_type = 'vungle'


# ============================================================================
# TOP OFFERWALLS (7-26)
# ============================================================================

class AdscendWebhookView(BaseWebhookView):
    network_type = 'adscend'


class OfferToroWebhookView(BaseWebhookView):
    network_type = 'offertoro'


class AdGemWebhookView(BaseWebhookView):
    network_type = 'adgem'


class AyetStudiosWebhookView(BaseWebhookView):
    network_type = 'ayetstudios'


class LootablyWebhookView(BaseWebhookView):
    network_type = 'lootably'


class RevenueUniverseWebhookView(BaseWebhookView):
    network_type = 'revenueuniverse'


class AdGateWebhookView(BaseWebhookView):
    network_type = 'adgate'


class CPAleadWebhookView(BaseWebhookView):
    network_type = 'cpalead'


class AdWorkMediaWebhookView(BaseWebhookView):
    network_type = 'adworkmedia'


class WannadsWebhookView(BaseWebhookView):
    network_type = 'wannads'


class PersonaLyWebhookView(BaseWebhookView):
    network_type = 'personaly'


class KiwiWallWebhookView(BaseWebhookView):
    network_type = 'kiwiwall'


class MonlixWebhookView(BaseWebhookView):
    network_type = 'monlix'


class NotikWebhookView(BaseWebhookView):
    network_type = 'notik'


class OfferDaddyWebhookView(BaseWebhookView):
    network_type = 'offerdaddy'


class OfferTownWebhookView(BaseWebhookView):
    network_type = 'offertown'


class AdLockMediaWebhookView(BaseWebhookView):
    network_type = 'adlockmedia'


class OfferwallProWebhookView(BaseWebhookView):
    network_type = 'offerwallpro'


class WallAdsWebhookView(BaseWebhookView):
    network_type = 'wallads'


class WallportWebhookView(BaseWebhookView):
    network_type = 'wallport'


class WallToroWebhookView(BaseWebhookView):
    network_type = 'walltoro'


# ============================================================================
# SURVEY SPECIALISTS (27-41)
# ============================================================================

class PollfishWebhookView(BaseWebhookView):
    network_type = 'pollfish'


class CPXResearchWebhookView(BaseWebhookView):
    network_type = 'cpxresearch'


class BitLabsWebhookView(BaseWebhookView):
    network_type = 'bitlabs'


class InBrainWebhookView(BaseWebhookView):
    network_type = 'inbrain'


class TheoremReachWebhookView(BaseWebhookView):
    network_type = 'theoremreach'


class YourSurveysWebhookView(BaseWebhookView):
    network_type = 'yoursurveys'


class SurveySavvyWebhookView(BaseWebhookView):
    network_type = 'surveysavvy'


class OpinionWorldWebhookView(BaseWebhookView):
    network_type = 'opinionworld'


class TolunaWebhookView(BaseWebhookView):
    network_type = 'toluna'


class SurveyMonkeyWebhookView(BaseWebhookView):
    network_type = 'surveymonkey'


class SwagbucksWebhookView(BaseWebhookView):
    network_type = 'swagbucks'


class PrizeRebelWebhookView(BaseWebhookView):
    network_type = 'prizerebel'


class GrabPointsWebhookView(BaseWebhookView):
    network_type = 'grabpoints'


class InstaGCWebhookView(BaseWebhookView):
    network_type = 'instagc'


class Points2ShopWebhookView(BaseWebhookView):
    network_type = 'points2shop'


# ============================================================================
# VIDEO & EASY TASKS (42-56)
# ============================================================================

class LootTVWebhookView(BaseWebhookView):
    network_type = 'loottv'


class HideoutTVWebhookView(BaseWebhookView):
    network_type = 'hideouttv'


class RewardRackWebhookView(BaseWebhookView):
    network_type = 'rewardrack'


class EarnHoneyWebhookView(BaseWebhookView):
    network_type = 'earnhoney'


class RewardXPWebhookView(BaseWebhookView):
    network_type = 'rewardxp'


class IdleEmpireWebhookView(BaseWebhookView):
    network_type = 'idleempire'


class GainWebhookView(BaseWebhookView):
    network_type = 'gain'


class GrindaBuckWebhookView(BaseWebhookView):
    network_type = 'grindabuck'


class TimeBucksWebhookView(BaseWebhookView):
    network_type = 'timebucks'


class ClixSenseWebhookView(BaseWebhookView):
    network_type = 'clixsense'


class NeoBuxWebhookView(BaseWebhookView):
    network_type = 'neobux'


class ProBuxWebhookView(BaseWebhookView):
    network_type = 'probux'


class ClixWallWebhookView(BaseWebhookView):
    network_type = 'clixwall'


class FyberWebhookView(BaseWebhookView):
    network_type = 'fyber'


class OfferStationWebhookView(BaseWebhookView):
    network_type = 'offerstation'


# ============================================================================
# GAMING & APP INSTALL (57-70)
# ============================================================================

class ChartboostWebhookView(BaseWebhookView):
    network_type = 'chartboost'


class SupersonicWebhookView(BaseWebhookView):
    network_type = 'supersonic'


class AppNextWebhookView(BaseWebhookView):
    network_type = 'appnext'


class DigitalTurbineWebhookView(BaseWebhookView):
    network_type = 'digitalturbine'


class GlispaWebhookView(BaseWebhookView):
    network_type = 'glispa'


class AdColonyWebhookView(BaseWebhookView):
    network_type = 'adcolony'


class InMobiWebhookView(BaseWebhookView):
    network_type = 'inmobi'


class MoPubWebhookView(BaseWebhookView):
    network_type = 'mopub'


class PangleWebhookView(BaseWebhookView):
    network_type = 'pangle'


class MintegralWebhookView(BaseWebhookView):
    network_type = 'mintegral'


class OguryWebhookView(BaseWebhookView):
    network_type = 'ogury'


class VerizonMediaWebhookView(BaseWebhookView):
    network_type = 'verizonmedia'


class SmaatoWebhookView(BaseWebhookView):
    network_type = 'smaato'


class MobileFuseWebhookView(BaseWebhookView):
    network_type = 'mobilefuse'


# ============================================================================
# MORE NETWORKS (71-80)
# ============================================================================

class LeadboltWebhookView(BaseWebhookView):
    network_type = 'leadbolt'


class StartAppWebhookView(BaseWebhookView):
    network_type = 'startapp'


class MediabrixWebhookView(BaseWebhookView):
    network_type = 'mediabrix'


class NativeXWebhookView(BaseWebhookView):
    network_type = 'nativex'


class HeyzapWebhookView(BaseWebhookView):
    network_type = 'heyzap'


class KidozWebhookView(BaseWebhookView):
    network_type = 'kidoz'


class PokktWebhookView(BaseWebhookView):
    network_type = 'pokkt'


class YouAppiWebhookView(BaseWebhookView):
    network_type = 'youappi'


class AmpiriWebhookView(BaseWebhookView):
    network_type = 'ampiri'


class AdinCubeWebhookView(BaseWebhookView):
    network_type = 'adincube'


# ============================================================================
# FUTURE EXPANSION (81-90)
# ============================================================================

class CustomNetwork1WebhookView(BaseWebhookView):
    network_type = 'custom1'


class CustomNetwork2WebhookView(BaseWebhookView):
    network_type = 'custom2'


class CustomNetwork3WebhookView(BaseWebhookView):
    network_type = 'custom3'


class CustomNetwork4WebhookView(BaseWebhookView):
    network_type = 'custom4'


class CustomNetwork5WebhookView(BaseWebhookView):
    network_type = 'custom5'


