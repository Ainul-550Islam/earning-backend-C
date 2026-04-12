"""database_models/offer_model.py — Typed proxy for OfferPostback model."""
from ..models import OfferPostback

class OfferModel:
    Model = OfferPostback

    @staticmethod
    def get_active_for_network(network):
        return OfferPostback.objects.filter(network=network, is_active=True)

    @staticmethod
    def get_by_offer_id(network, offer_id):
        return OfferPostback.objects.filter(network=network, offer_id=offer_id).first()

    @staticmethod
    def count_active():
        return OfferPostback.objects.filter(is_active=True).count()

    @staticmethod
    def get_allowed_countries(network, offer_id) -> list:
        offer = OfferModel.get_by_offer_id(network, offer_id)
        return offer.allowed_countries if offer else []
