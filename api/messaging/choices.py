"""
Messaging Choices — All Django TextChoices enums used across the messaging module.
World-class update: added Reaction, Call, Notification, Priority, Channel types.
"""

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


# ── Existing (unchanged) ─────────────────────────────────────────────────────

class ChatStatus(TextChoices):
    ACTIVE   = "ACTIVE",   _("Active")
    ARCHIVED = "ARCHIVED", _("Archived")
    DELETED  = "DELETED",  _("Deleted")


class MessageStatus(TextChoices):
    SENT      = "SENT",      _("Sent")
    DELIVERED = "DELIVERED", _("Delivered")
    READ      = "READ",      _("Read")
    FAILED    = "FAILED",    _("Failed")
    DELETED   = "DELETED",   _("Deleted")


class BroadcastStatus(TextChoices):
    DRAFT     = "DRAFT",     _("Draft")
    SCHEDULED = "SCHEDULED", _("Scheduled")
    SENDING   = "SENDING",   _("Sending")
    SENT      = "SENT",      _("Sent")
    FAILED    = "FAILED",    _("Failed")
    CANCELLED = "CANCELLED", _("Cancelled")


class BroadcastAudienceType(TextChoices):
    ALL_USERS      = "ALL_USERS",      _("All Users")
    ACTIVE_USERS   = "ACTIVE_USERS",   _("Active Users")
    SPECIFIC_USERS = "SPECIFIC_USERS", _("Specific Users")
    USER_GROUP     = "USER_GROUP",     _("User Group")


class SupportThreadStatus(TextChoices):
    OPEN         = "OPEN",         _("Open")
    IN_PROGRESS  = "IN_PROGRESS",  _("In Progress")
    WAITING_USER = "WAITING_USER", _("Waiting for User")
    RESOLVED     = "RESOLVED",     _("Resolved")
    CLOSED       = "CLOSED",       _("Closed")


class SupportThreadPriority(TextChoices):
    LOW    = "LOW",    _("Low")
    NORMAL = "NORMAL", _("Normal")
    HIGH   = "HIGH",   _("High")
    URGENT = "URGENT", _("Urgent")


class InboxItemType(TextChoices):
    CHAT_MESSAGE   = "CHAT_MESSAGE",   _("Chat Message")
    BROADCAST      = "BROADCAST",      _("Broadcast")
    SUPPORT_REPLY  = "SUPPORT_REPLY",  _("Support Reply")
    SYSTEM         = "SYSTEM",         _("System Notification")
    REACTION       = "REACTION",       _("Message Reaction")    # NEW
    MENTION        = "MENTION",        _("Mention")             # NEW
    CALL_MISSED    = "CALL_MISSED",    _("Missed Call")         # NEW
    ANNOUNCEMENT   = "ANNOUNCEMENT",  _("Announcement")        # NEW


class MessageType(TextChoices):
    TEXT       = "TEXT",       _("Text")
    IMAGE      = "IMAGE",      _("Image")
    FILE       = "FILE",       _("File")
    SYSTEM     = "SYSTEM",     _("System")
    AUDIO      = "AUDIO",      _("Audio")      # NEW
    VIDEO      = "VIDEO",      _("Video")      # NEW
    STICKER    = "STICKER",    _("Sticker")    # NEW
    LOCATION   = "LOCATION",   _("Location")   # NEW
    CONTACT    = "CONTACT",    _("Contact")    # NEW
    POLL       = "POLL",       _("Poll")       # NEW
    CALL_LOG   = "CALL_LOG",   _("Call Log")   # NEW
    GIF        = "GIF",        _("GIF")        # NEW
    BOT        = "BOT",        _("Bot Message")# NEW


class ParticipantRole(TextChoices):
    MEMBER = "MEMBER", _("Member")
    ADMIN  = "ADMIN",  _("Admin")
    OWNER  = "OWNER",  _("Owner")


# ── New Choices ───────────────────────────────────────────────────────────────

class ReactionEmoji(TextChoices):
    """Standard emoji reactions — like Slack/Discord/WhatsApp."""
    THUMBS_UP   = "👍", _("Thumbs Up")
    THUMBS_DOWN = "👎", _("Thumbs Down")
    HEART       = "❤️",  _("Heart")
    LAUGH       = "😂", _("Laugh")
    WOW         = "😮", _("Wow")
    SAD         = "😢", _("Sad")
    ANGRY       = "😠", _("Angry")
    FIRE        = "🔥", _("Fire")
    CLAP        = "👏", _("Clap")
    CHECK       = "✅", _("Check")
    CUSTOM      = "CUSTOM", _("Custom Emoji")


class CallStatus(TextChoices):
    """Voice/Video call states."""
    RINGING   = "RINGING",   _("Ringing")
    ONGOING   = "ONGOING",   _("Ongoing")
    ENDED     = "ENDED",     _("Ended")
    MISSED    = "MISSED",    _("Missed")
    DECLINED  = "DECLINED",  _("Declined")
    FAILED    = "FAILED",    _("Failed")
    NO_ANSWER = "NO_ANSWER", _("No Answer")


class CallType(TextChoices):
    AUDIO = "AUDIO", _("Audio Call")
    VIDEO = "VIDEO", _("Video Call")


class NotificationPreference(TextChoices):
    ALL      = "ALL",      _("All Notifications")
    MENTIONS = "MENTIONS", _("Mentions Only")
    NONE     = "NONE",     _("Muted")


class PresenceStatus(TextChoices):
    ONLINE  = "ONLINE",  _("Online")
    AWAY    = "AWAY",    _("Away")
    BUSY    = "BUSY",    _("Busy")
    OFFLINE = "OFFLINE", _("Offline")


class ChannelType(TextChoices):
    """Announcement channel types (one-way broadcast, like Telegram channels)."""
    PUBLIC  = "PUBLIC",  _("Public Channel")
    PRIVATE = "PRIVATE", _("Private Channel")


class BotTriggerType(TextChoices):
    KEYWORD  = "KEYWORD",  _("Keyword Match")
    REGEX    = "REGEX",    _("Regex Match")
    ALWAYS   = "ALWAYS",   _("Always Respond")
    NEW_USER = "NEW_USER", _("New User Greeting")


class MessagePriority(TextChoices):
    LOW    = "LOW",    _("Low")
    NORMAL = "NORMAL", _("Normal")
    HIGH   = "HIGH",   _("High")
    URGENT = "URGENT", _("Urgent (Push)")


class WebhookEventType(TextChoices):
    MESSAGE_SENT    = "message.sent",    _("Message Sent")
    MESSAGE_DELETED = "message.deleted", _("Message Deleted")
    CHAT_CREATED    = "chat.created",    _("Chat Created")
    USER_JOINED     = "user.joined",     _("User Joined")
    USER_LEFT       = "user.left",       _("User Left")
    BROADCAST_SENT  = "broadcast.sent",  _("Broadcast Sent")
    SUPPORT_OPENED  = "support.opened",  _("Support Thread Opened")
    SUPPORT_CLOSED  = "support.closed",  _("Support Thread Closed")
    CALL_STARTED    = "call.started",    _("Call Started")
    CALL_ENDED      = "call.ended",      _("Call Ended")


class ScheduledMessageStatus(TextChoices):
    PENDING   = "PENDING",   _("Pending")
    SENT      = "SENT",      _("Sent")
    CANCELLED = "CANCELLED", _("Cancelled")
    FAILED    = "FAILED",    _("Failed")


# ── Story choices (new) ───────────────────────────────────────────────────────

class StoryType(TextChoices):
    TEXT  = "text",  _("Text")
    IMAGE = "image", _("Image")
    VIDEO = "video", _("Video")


class StoryVisibility(TextChoices):
    ALL      = "all",      _("All Contacts")
    CLOSE    = "close",    _("Close Friends")
    EXCEPT   = "except",   _("All Except...")
    SELECTED = "selected", _("Selected Only")


class STTProvider(TextChoices):
    WHISPER = "whisper", _("OpenAI Whisper")
    GOOGLE  = "google",  _("Google STT")
    AZURE   = "azure",   _("Azure Speech")


# ── CPA Platform Notification Types (CPAlead-style) ───────────────────────────

class CPANotificationType(TextChoices):
    """All notification types specific to a CPA affiliate platform."""
    # Offer events
    OFFER_APPROVED          = "offer.approved",       _("Offer Approved")
    OFFER_REJECTED          = "offer.rejected",       _("Offer Rejected")
    OFFER_PAUSED            = "offer.paused",         _("Offer Paused — Cap Reached")
    OFFER_REACTIVATED       = "offer.reactivated",    _("Offer Reactivated")
    NEW_OFFER_AVAILABLE     = "offer.new",            _("New Offer Available")
    OFFER_EXPIRING_SOON     = "offer.expiring",       _("Offer Expiring Soon")

    # Conversion / lead events
    CONVERSION_RECEIVED     = "conversion.received",  _("New Conversion")
    CONVERSION_APPROVED     = "conversion.approved",  _("Conversion Approved")
    CONVERSION_REJECTED     = "conversion.rejected",  _("Conversion Rejected")
    CONVERSION_CHARGEBACK   = "conversion.chargeback",_("Conversion Chargeback")
    POSTBACK_FAILED         = "postback.failed",      _("Postback Delivery Failed")

    # Payout events
    PAYOUT_PROCESSED        = "payout.processed",     _("Payout Processed")
    PAYOUT_PENDING_REMINDER = "payout.reminder",      _("Payout Due Tomorrow")
    PAYOUT_THRESHOLD_MET    = "payout.threshold",     _("Payout Threshold Reached")
    PAYOUT_FAILED           = "payout.failed",        _("Payout Failed")
    PAYOUT_ON_HOLD          = "payout.hold",          _("Payout On Hold")

    # Affiliate account events
    AFFILIATE_APPROVED      = "affiliate.approved",   _("Affiliate Account Approved")
    AFFILIATE_REJECTED      = "affiliate.rejected",   _("Affiliate Account Rejected")
    AFFILIATE_SUSPENDED     = "affiliate.suspended",  _("Account Suspended")
    AFFILIATE_REINSTATED    = "affiliate.reinstated", _("Account Reinstated")
    AFFILIATE_BANNED        = "affiliate.banned",     _("Account Permanently Banned")
    MANAGER_ASSIGNED        = "affiliate.manager",    _("Account Manager Assigned")

    # Performance / milestones
    MILESTONE_REACHED       = "milestone.reached",    _("Performance Milestone Reached")
    EPC_DROP_ALERT          = "epc.drop",             _("EPC Drop Alert")
    FRAUD_ALERT             = "fraud.alert",          _("Fraud Warning")

    # System
    SYSTEM_MAINTENANCE      = "system.maintenance",   _("Scheduled Maintenance")
    SYSTEM_ANNOUNCEMENT     = "system.announcement",  _("Platform Announcement")
    API_KEY_EXPIRING        = "api.key_expiring",     _("API Key Expiring")
    TERMS_UPDATED           = "terms.updated",        _("Terms of Service Updated")


class CPABroadcastAudienceFilter(TextChoices):
    """CPAlead-style audience targeting for broadcasts."""
    ALL_AFFILIATES          = "all",         _("All Affiliates")
    BY_OFFER                = "by_offer",    _("Affiliates Running Specific Offer")
    BY_VERTICAL             = "by_vertical", _("Affiliates by Vertical")
    BY_COUNTRY              = "by_country",  _("Affiliates by Country/GEO")
    BY_TIER                 = "by_tier",     _("Affiliates by Account Tier")
    BY_MANAGER              = "by_manager",  _("Affiliates by Account Manager")
    BY_EARNINGS             = "by_earnings", _("Affiliates by Earnings Range")
    TOP_PERFORMERS          = "top",         _("Top 10% Performers")
    NEW_AFFILIATES          = "new",         _("New Affiliates (last 30 days)")
    INACTIVE                = "inactive",    _("Inactive Affiliates (60+ days)")


class NotificationPriority(TextChoices):
    LOW     = "LOW",     _("Low")
    NORMAL  = "NORMAL",  _("Normal")
    HIGH    = "HIGH",    _("High — Push immediately")
    URGENT  = "URGENT",  _("Urgent — SMS + Email + Push")


class MessageTemplateCategory(TextChoices):
    OFFER       = "offer",       _("Offer-Related")
    PAYOUT      = "payout",      _("Payout-Related")
    ACCOUNT     = "account",     _("Account Status")
    PERFORMANCE = "performance", _("Performance")
    SYSTEM      = "system",      _("System")
    CUSTOM      = "custom",      _("Custom")
