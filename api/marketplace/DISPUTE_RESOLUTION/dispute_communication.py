"""
DISPUTE_RESOLUTION/dispute_communication.py — Dispute Thread Messaging
"""
from .dispute_model import Dispute, DisputeMessage


def send_message(dispute: Dispute, sender, role: str, body: str, is_internal: bool = False) -> DisputeMessage:
    if dispute.status in ("resolved_buyer","resolved_seller","closed") and not is_internal:
        raise ValueError("Dispute is resolved — messaging closed")
    return DisputeMessage.objects.create(
        tenant=dispute.tenant, dispute=dispute,
        sender=sender, role=role, body=body, is_internal=is_internal,
    )


def get_thread(dispute: Dispute, include_internal: bool = False) -> list:
    qs = DisputeMessage.objects.filter(dispute=dispute)
    if not include_internal:
        qs = qs.filter(is_internal=False)
    return [
        {
            "id":          m.pk,
            "role":        m.role,
            "sender":      m.sender.username if m.sender else "System",
            "body":        m.body,
            "is_internal": m.is_internal,
            "sent_at":     m.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for m in qs.order_by("created_at")
    ]


def notify_parties(dispute: Dispute, event: str, actor_role: str):
    """Send email/push notifications to all parties."""
    from api.marketplace.INTEGRATIONS.email_service import send_order_confirmation_email
    from api.marketplace.MOBILE_MARKETPLACE.push_notification import PushNotificationService
    push = PushNotificationService()
    msg_map = {
        "new_message":   "New message in your dispute",
        "seller_replied":"Seller has responded to your dispute",
        "admin_review":  "Admin is reviewing your dispute",
        "resolved":      "Your dispute has been resolved",
    }
    push_msg = msg_map.get(event, "Dispute update")
    # Notify buyer
    if dispute.raised_by:
        push.send_to_user(dispute.raised_by, "Dispute Update", push_msg,
                           data={"dispute_id": dispute.pk, "type": "dispute_update"})
    # Notify seller
    if dispute.against_seller and dispute.against_seller.user:
        push.send_to_user(dispute.against_seller.user, "Dispute Update", push_msg,
                           data={"dispute_id": dispute.pk, "type": "dispute_update"})
