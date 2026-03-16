"""
Persona.ly survey processor
"""
import hashlib
import logging

from api.offerwall.exceptions import InvalidWebhookSignatureException
from .OfferProcessor import OfferProcessor
from ..constants import *

logger = logging.getLogger(__name__)


class PersonaService(OfferProcessor):
    """Persona.ly survey processor"""
    
    def __init__(self, provider):
        super().__init__(provider)
        self.api_key = provider.api_key
        self.secret_key = provider.secret_key
    
    def fetch_offers(self, **kwargs):
        """Persona doesn't provide offer list API, returns empty"""
        return []
    
    def parse_offer_data(self, raw_data):
        """Parse Persona survey data"""
        return {
            'external_offer_id': str(raw_data.get('survey_id', '')),
            'title': raw_data.get('survey_name', 'Complete Survey'),
            'description': 'Answer questions and earn rewards',
            'payout': self.validate_payout(raw_data.get('payout', 0)),
            'currency': 'USD',
            'offer_type': OFFER_TYPE_SURVEY,
            'platform': PLATFORM_ALL,
            'estimated_time_minutes': raw_data.get('loi', 10),
            'status': STATUS_ACTIVE,
            'metadata': {'persona_survey_id': raw_data.get('survey_id')}
        }
    
    def build_click_url(self, offer, user):
        """Build Persona survey URL"""
        return f"https://persona.ly/survey?api_key={self.api_key}&user_id={user.id}"
    
    def verify_postback(self, data):
        """Verify Persona postback"""
        if not self.secret_key:
            return True
        sig = data.get('hash', '')
        if not sig:
            raise InvalidWebhookSignatureException("No signature")
        verify_str = f"{data.get('user_id')}{data.get('survey_id')}{data.get('payout')}{self.secret_key}"
        expected = hashlib.md5(verify_str.encode()).hexdigest()
        if sig != expected:
            raise InvalidWebhookSignatureException("Invalid signature")
        return True


from .OfferProcessor import OfferProcessorFactory
OfferProcessorFactory.register(PROVIDER_PERSONA, PersonaService)