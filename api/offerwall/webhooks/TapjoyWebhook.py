"""
Tapjoy webhook handler
"""
import logging
from django.views import View
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class TapjoyWebhookView(View):
    """Handle Tapjoy postback callbacks"""
    
    def post(self, request):
        """Process Tapjoy conversion postback"""
        try:
            # Lazy imports to avoid circular dependency
            from ..models import OfferProvider, Offer, OfferConversion
            from api.users.models import User
            from ..services.TapjoyService import TapjoyService
            from ..utils.RewardCalculator import RewardCalculator
            
            # Get provider
            provider = OfferProvider.objects.get(provider_type='tapjoy', status='active')
            service = TapjoyService(provider)
            
            # Get postback data
            data = {
                'id': request.POST.get('id'),
                'snuid': request.POST.get('snuid'),  # user_id
                'currency': request.POST.get('currency'),
                'verifier': request.POST.get('verifier'),
            }
            
            # Verify signature
            service.verify_postback(data)
            
            # Get user and offer
            user_id = data['snuid']
            offer_id = data['id']
            payout = float(data['currency'])
            
            user = User.objects.get(id=user_id)
            offer = Offer.objects.get(external_offer_id=offer_id, provider=provider)
            
            # Calculate reward
            calculator = RewardCalculator(offer, provider)
            reward_data = calculator.calculate_total_reward(payout)
            
            # Create conversion
            conversion = OfferConversion.objects.create(
                offer=offer,
                user=user,
                conversion_id=f"tapjoy_{data['id']}_{user_id}",
                external_transaction_id=data['id'],
                payout_amount=payout,
                payout_currency='USD',
                reward_amount=reward_data['total_reward'],
                reward_currency=offer.reward_currency,
                status='pending',
                postback_data=data
            )
            
            # Auto-approve if configured
            if provider.config.get('auto_approve', False):
                conversion.approve()
            
            logger.info(f"Tapjoy conversion created: {conversion.conversion_id}")
            
            return HttpResponse('OK', status=200)
        
        except Exception as e:
            logger.error(f"Tapjoy webhook error: {e}")
            return HttpResponse(f'Error: {str(e)}', status=400)