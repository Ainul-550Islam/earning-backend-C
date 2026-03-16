"""
Messaging Choices — All Django TextChoices enums used across the messaging module.
"""

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class ChatStatus(TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    ARCHIVED = "ARCHIVED", _("Archived")
    DELETED = "DELETED", _("Deleted")


class MessageStatus(TextChoices):
    SENT = "SENT", _("Sent")
    DELIVERED = "DELIVERED", _("Delivered")
    READ = "READ", _("Read")
    FAILED = "FAILED", _("Failed")
    DELETED = "DELETED", _("Deleted")


class BroadcastStatus(TextChoices):
    DRAFT = "DRAFT", _("Draft")
    SCHEDULED = "SCHEDULED", _("Scheduled")
    SENDING = "SENDING", _("Sending")
    SENT = "SENT", _("Sent")
    FAILED = "FAILED", _("Failed")
    CANCELLED = "CANCELLED", _("Cancelled")


class BroadcastAudienceType(TextChoices):
    ALL_USERS = "ALL_USERS", _("All Users")
    ACTIVE_USERS = "ACTIVE_USERS", _("Active Users")
    SPECIFIC_USERS = "SPECIFIC_USERS", _("Specific Users")
    USER_GROUP = "USER_GROUP", _("User Group")


class SupportThreadStatus(TextChoices):
    OPEN = "OPEN", _("Open")
    IN_PROGRESS = "IN_PROGRESS", _("In Progress")
    WAITING_USER = "WAITING_USER", _("Waiting for User")
    RESOLVED = "RESOLVED", _("Resolved")
    CLOSED = "CLOSED", _("Closed")


class SupportThreadPriority(TextChoices):
    LOW = "LOW", _("Low")
    NORMAL = "NORMAL", _("Normal")
    HIGH = "HIGH", _("High")
    URGENT = "URGENT", _("Urgent")


class InboxItemType(TextChoices):
    CHAT_MESSAGE = "CHAT_MESSAGE", _("Chat Message")
    BROADCAST = "BROADCAST", _("Broadcast")
    SUPPORT_REPLY = "SUPPORT_REPLY", _("Support Reply")
    SYSTEM = "SYSTEM", _("System Notification")


class MessageType(TextChoices):
    TEXT = "TEXT", _("Text")
    IMAGE = "IMAGE", _("Image")
    FILE = "FILE", _("File")
    SYSTEM = "SYSTEM", _("System")


class ParticipantRole(TextChoices):
    MEMBER = "MEMBER", _("Member")
    ADMIN = "ADMIN", _("Admin")
    OWNER = "OWNER", _("Owner")
