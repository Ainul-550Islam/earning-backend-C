"""Task services stub: cap."""
from celery import shared_task


# Auto-generated re-exports for task imports
try:
    from offer_routing.services.cap.CapEnforcementService import CapEnforcementService
except ImportError:
    CapEnforcementService = None
try:
    from offer_routing.services.cap.CapResetService import CapResetService
except ImportError:
    CapResetService = None
