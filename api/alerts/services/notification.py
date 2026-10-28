"""
alerts/services/notification.py
Re-exports NotificationService from services/channel so that
services/incident/incident_manager.py (which imports from here) works correctly.
"""
from .channel import NotificationService, ChannelRoutingService, ChannelHealthService

__all__ = ['NotificationService', 'ChannelRoutingService', 'ChannelHealthService']
