# earning_backend/api/notifications/interactors.py
"""
Interactors — Thin orchestration layer between views and use cases.
Translates HTTP request data into use case inputs and formats responses.

In some architectures these are called "services" at the view layer.
Here they bridge ViewSets ↔ UseCases cleanly.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class NotificationInteractor:
    """Orchestrates notification-related use cases for ViewSets."""

    def send_notification(self, *, user, data: Dict) -> Dict:
        from notifications.use_cases import SendNotificationUseCase
        result = SendNotificationUseCase().execute(
            user=user,
            title=data.get("title", ""),
            message=data.get("message", ""),
            notification_type=data.get("notification_type", "announcement"),
            channel=data.get("channel", "in_app"),
            priority=data.get("priority", "medium"),
            action_url=data.get("action_url", ""),
            metadata=data.get("metadata", {}),
            scheduled_at=data.get("scheduled_at"),
            template_id=data.get("template_id"),
        )
        return {"success": result.success, "data": result.data, "error": result.error}

    def mark_read(self, *, user, notification_id: int = None, mark_all: bool = False) -> Dict:
        from notifications.use_cases import MarkNotificationReadUseCase
        result = MarkNotificationReadUseCase().execute(user=user, notification_id=notification_id, mark_all=mark_all)
        return {"success": result.success, "data": result.data, "error": result.error}

    def delete_notification(self, *, user, notification_id: int) -> Dict:
        from notifications.use_cases import DeleteNotificationUseCase
        result = DeleteNotificationUseCase().execute(user=user, notification_id=notification_id)
        return {"success": result.success, "data": result.data, "error": result.error}

    def register_device(self, *, user, data: Dict) -> Dict:
        from notifications.use_cases import RegisterPushDeviceUseCase
        result = RegisterPushDeviceUseCase().execute(
            user=user,
            device_type=data.get("device_type", "android"),
            fcm_token=data.get("fcm_token", ""),
            apns_token=data.get("apns_token", ""),
            web_push_subscription=data.get("web_push_subscription", {}),
            device_name=data.get("device_name", ""),
            app_version=data.get("app_version", ""),
        )
        return {"success": result.success, "data": result.data, "error": result.error}

    def opt_out(self, *, user, channel: str, reason: str = "user_request", notes: str = "") -> Dict:
        from notifications.use_cases import OptOutChannelUseCase
        result = OptOutChannelUseCase().execute(user=user, channel=channel, reason=reason, notes=notes)
        return {"success": result.success, "data": result.data, "error": result.error}

    def bulk_send(self, *, user_ids: list, data: Dict) -> Dict:
        from notifications.use_cases import BulkSendNotificationUseCase
        result = BulkSendNotificationUseCase().execute(
            user_ids=user_ids,
            title=data.get("title", ""),
            message=data.get("message", ""),
            notification_type=data.get("notification_type", "announcement"),
            channel=data.get("channel", "in_app"),
            priority=data.get("priority", "medium"),
        )
        return {"success": result.success, "data": result.data, "error": result.error}

    def create_campaign(self, *, created_by, data: Dict) -> Dict:
        from notifications.use_cases import CreateCampaignUseCase
        result = CreateCampaignUseCase().execute(
            created_by=created_by,
            name=data.get("name", ""),
            template_id=data.get("template_id"),
            segment_conditions=data.get("segment_conditions", {}),
            send_at=data.get("send_at"),
            description=data.get("description", ""),
        )
        return {"success": result.success, "data": result.data, "error": result.error}

    def enroll_journey(self, *, user, journey_id: str, context: Dict = None) -> Dict:
        from notifications.use_cases import EnrollUserInJourneyUseCase
        result = EnrollUserInJourneyUseCase().execute(user=user, journey_id=journey_id, context=context or {})
        return {"success": result.success, "data": result.data, "error": result.error}

    def update_preferences(self, *, user, data: Dict) -> Dict:
        from notifications.use_cases import UpdatePreferencesUseCase
        result = UpdatePreferencesUseCase().execute(user=user, preferences=data)
        return {"success": result.success, "data": result.data, "error": result.error}


notification_interactor = NotificationInteractor()
