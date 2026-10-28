"""
alerts/services/incident/__init__.py
Exports IncidentManager from incident_manager.py and wires it into the service layer.
Previously this file was empty — causing IncidentViewSet to bypass the service layer entirely.
"""
import logging

logger = logging.getLogger(__name__)

try:
    from .incident_manager import IncidentManager
except Exception as _e:
    logger.warning('api.alerts.services.incident: could not import IncidentManager: %s', _e)

    class IncidentManager:
        """Stub IncidentManager when real import fails"""
        def create_incident(self, *args, **kwargs):
            raise NotImplementedError('IncidentManager import failed — check logs')

        def acknowledge_incident(self, *args, **kwargs):
            raise NotImplementedError('IncidentManager import failed — check logs')

        def resolve_incident(self, *args, **kwargs):
            raise NotImplementedError('IncidentManager import failed — check logs')

        def close_incident(self, *args, **kwargs):
            raise NotImplementedError('IncidentManager import failed — check logs')

        def escalate_incident(self, *args, **kwargs):
            raise NotImplementedError('IncidentManager import failed — check logs')


__all__ = ['IncidentManager']
