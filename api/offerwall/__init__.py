"""
api/offerwall/__init__.py
Offerwall module — lazy public API surface.

Imports deferred to avoid circular import during Django app registry setup.
Use direct imports in application code:
    from api.offerwall.models import Offer
    from api.offerwall.services.OfferwallIntegrationService import OfferwallIntegrationService
"""
default_app_config = 'api.offerwall.apps.OfferwallConfig'
