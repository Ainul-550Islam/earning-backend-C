"""
OfferToro webhook handler
"""
import logging
from django.views import View
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class OfferwallWebhookView(View):
    """Handle OfferToro postback"""
    
    def get(self, request):
        """Process OfferToro postback"""
        try:
            # Lazy imports
            from ..models import OfferProvider, Offer, OfferConversion
            from api.users.models import User
            from ..services.OfferwallService import OfferwallService
            from ..utils.RewardCalculator import RewardCalculator
            
            provider = OfferProvider.objects.get(provider_type='offerwall', status='active')
            service = OfferwallService(provider)
            
            data = {
                'oid': request.GET.get('oid'),
                'user_id': request.GET.get('user_id'),
                'amount': request.GET.get('amount'),
                'sig': request.GET.get('sig'),
            }
            
            service.verify_postback(data)
            
            user = User.objects.get(id=data['user_id'])
            offer = Offer.objects.get(external_offer_id=data['oid'], provider=provider)
            
            calculator = RewardCalculator(offer, provider)
            reward_data = calculator.calculate_total_reward(float(data['amount']))
            
            conversion = OfferConversion.objects.create(
                offer=offer,
                user=user,
                conversion_id=f"offertoro_{data['oid']}_{data['user_id']}",
                external_transaction_id=data['oid'],
                payout_amount=float(data['amount']),
                payout_currency='USD',
                reward_amount=reward_data['total_reward'],
                reward_currency=offer.reward_currency,
                status='pending',
                postback_data=data
            )
            
            if provider.config.get('auto_approve', False):
                conversion.approve()
            
            logger.info(f"OfferToro conversion: {conversion.conversion_id}")
            
            return HttpResponse('1', status=200)
        
        except Exception as e:
            logger.error(f"OfferToro webhook error: {e}")
            return HttpResponse('0', status=400)