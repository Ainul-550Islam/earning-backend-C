"""
Payout Queue Choices — All Django TextChoices enums.
"""

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class PayoutBatchStatus(TextChoices):
    PENDING = "PENDING", _("Pending")
    PROCESSING = "PROCESSING", _("Processing")
    COMPLETED = "COMPLETED", _("Completed")
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED", _("Partially Completed")
    FAILED = "FAILED", _("Failed")
    CANCELLED = "CANCELLED", _("Cancelled")
    ON_HOLD = "ON_HOLD", _("On Hold")


class PayoutItemStatus(TextChoices):
    QUEUED = "QUEUED", _("Queued")
    PROCESSING = "PROCESSING", _("Processing")
    SUCCESS = "SUCCESS", _("Success")
    FAILED = "FAILED", _("Failed")
    RETRYING = "RETRYING", _("Retrying")
    CANCELLED = "CANCELLED", _("Cancelled")
    SKIPPED = "SKIPPED", _("Skipped")


class PaymentGateway(TextChoices):
    BKASH = "BKASH", _("bKash")
    NAGAD = "NAGAD", _("Nagad")
    ROCKET = "ROCKET", _("Rocket")
    BANK = "BANK", _("Bank Transfer")
    MANUAL = "MANUAL", _("Manual")


class PriorityLevel(TextChoices):
    LOW = "LOW", _("Low")
    NORMAL = "NORMAL", _("Normal")
    HIGH = "HIGH", _("High")
    URGENT = "URGENT", _("Urgent")
    CRITICAL = "CRITICAL", _("Critical")


class BulkProcessLogStatus(TextChoices):
    STARTED = "STARTED", _("Started")
    SUCCESS = "SUCCESS", _("Success")
    PARTIAL = "PARTIAL", _("Partial Success")
    FAILED = "FAILED", _("Failed")


class FeeType(TextChoices):
    FLAT = "FLAT", _("Flat Fee")
    PERCENTAGE = "PERCENTAGE", _("Percentage")
    TIERED = "TIERED", _("Tiered")


class WithdrawalPriorityReason(TextChoices):
    USER_REQUEST = "USER_REQUEST", _("User Request")
    SLA_BREACH = "SLA_BREACH", _("SLA Breach")
    VIP_USER = "VIP_USER", _("VIP User")
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE", _("Admin Override")
    SYSTEM = "SYSTEM", _("System")
