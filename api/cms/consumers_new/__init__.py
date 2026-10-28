# cms/consumers_new/__init__.py
"""RealTimeOffer WebSocket consumers package."""
from .RealTimeOfferConsumer import RealTimeOfferConsumer, AdminRealTimeOfferConsumer

__all__ = ['RealTimeOfferConsumer', 'AdminRealTimeOfferConsumer']
