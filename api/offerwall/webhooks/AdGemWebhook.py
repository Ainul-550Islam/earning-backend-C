"""
AdGem webhook handler
"""
import logging
from django.views import View
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AdGemWebhookView(View):
    """Handle AdGem postback callbacks"""
    
    def get(self, request):
        """Process AdGem conversion postback"""
        try:
            # Lazy imports
            from ..models import OfferProvider, Offer, OfferConversion
            from api.users.models import User
            from ..services.AdGemService import AdGemService
            from ..utils.RewardCalculator import RewardCalculator
            
            provider = OfferProvider.objects.get(provider_type='adgem', status='active')
            service = AdGemService(provider)
            
            data = {
                'user_id': request.GET.get('user_id'),
                'offer_id': request.GET.get('offer_id'),
                'points': request.GET.get('points'),
                'signature': request.GET.get('signature'),
                'transaction_id': request.GET.get('transaction_id'),
            }
            
            service.verify_postback(data)
            
            user = User.objects.get(id=data['user_id'])
            offer = Offer.objects.get(external_offer_id=data['offer_id'], provider=provider)
            
            calculator = RewardCalculator(offer, provider)
            reward_data = calculator.calculate_total_reward(float(data['points']))
            
            conversion = OfferConversion.objects.create(
                offer=offer,
                user=user,
                conversion_id=f"adgem_{data['transaction_id']}",
                external_transaction_id=data['transaction_id'],
                payout_amount=float(data['points']),
                payout_currency='USD',
                reward_amount=reward_data['total_reward'],
                reward_currency=offer.reward_currency,
                status='pending',
                postback_data=data
            )
            
            if provider.config.get('auto_approve', False):
                conversion.approve()
            
            logger.info(f"AdGem conversion: {conversion.conversion_id}")
            
            return HttpResponse('1', status=200)
        
        except Exception as e:
            logger.error(f"AdGem webhook error: {e}")
            return HttpResponse('0', status=400)