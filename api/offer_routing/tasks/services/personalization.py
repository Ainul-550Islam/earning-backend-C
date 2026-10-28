"""Task services stub: personalization."""
from celery import shared_task


# Auto-generated re-exports for task imports
try:
    from offer_routing.services.personalization.CollaborativeFilterService import CollaborativeFilterService
except ImportError:
    CollaborativeFilterService = None
try:
    from offer_routing.services.personalization.ContextSignalService import ContextSignalService
except ImportError:
    ContextSignalService = None
