"""
Management command: create_cpa_templates
Creates default CPA notification message templates.
Run once after deployment: python manage.py create_cpa_templates
"""
from django.core.management.base import BaseCommand


TEMPLATES = [
    {
        "name": "Offer Approved — Standard",
        "category": "offer",
        "subject": "Your offer application has been approved: {offer_name}",
        "body": (
            "Hi {affiliate_name},\n\n"
            "Great news! Your application for the offer \"{offer_name}\" has been approved.\n\n"
            "Payout: {payout}\n"
            "Status: Active\n\n"
            "You can now start driving traffic. Log in to your dashboard to get your tracking links.\n\n"
            "Best regards,\n{manager_name}"
        ),
        "tags": ["offer", "approved"],
    },
    {
        "name": "Offer Rejected — Standard",
        "category": "offer",
        "subject": "Update on your offer application: {offer_name}",
        "body": (
            "Hi {affiliate_name},\n\n"
            "Thank you for your interest in \"{offer_name}\". Unfortunately, we are unable to "
            "approve your application at this time.\n\n"
            "If you have questions, please contact your account manager.\n\n"
            "Best regards,\n{manager_name}"
        ),
        "tags": ["offer", "rejected"],
    },
    {
        "name": "Payout Processed — Standard",
        "category": "payout",
        "subject": "Your payment of {amount} has been sent",
        "body": (
            "Hi {affiliate_name},\n\n"
            "Your payment of {amount} has been processed and is on its way!\n\n"
            "Payment method: {payment_method}\n"
            "Expected arrival: 3-5 business days\n\n"
            "Thank you for your hard work.\n\n"
            "Best regards,\n{manager_name}"
        ),
        "tags": ["payout", "processed"],
    },
    {
        "name": "Payout On Hold — Review",
        "category": "payout",
        "subject": "Action required: Your payout of {amount} is on hold",
        "body": (
            "Hi {affiliate_name},\n\n"
            "Your payout of {amount} has been placed on hold pending review.\n\n"
            "This may be due to unusual traffic patterns or account verification requirements.\n\n"
            "Please contact your account manager or submit a support ticket to resolve this.\n\n"
            "Best regards,\n{manager_name}"
        ),
        "tags": ["payout", "hold", "urgent"],
    },
    {
        "name": "Welcome — New Affiliate",
        "category": "account",
        "subject": "Welcome to the platform, {affiliate_name}!",
        "body": (
            "Hi {affiliate_name},\n\n"
            "Welcome! Your affiliate account has been approved.\n\n"
            "Your dedicated account manager is {manager_name}. "
            "Feel free to reach out at any time with questions.\n\n"
            "Get started by browsing our available offers.\n\n"
            "Best regards,\n{manager_name}"
        ),
        "tags": ["account", "welcome", "onboarding"],
    },
    {
        "name": "Account Suspended — Warning",
        "category": "account",
        "subject": "Important: Your account has been temporarily suspended",
        "body": (
            "Hi {affiliate_name},\n\n"
            "Your account has been temporarily suspended.\n\n"
            "If you believe this is an error or would like to appeal, "
            "please contact our support team immediately.\n\n"
            "Best regards,\nCompliance Team"
        ),
        "tags": ["account", "suspended", "urgent"],
    },
    {
        "name": "Fraud Warning — Traffic Quality",
        "category": "account",
        "subject": "Traffic quality warning on your campaign",
        "body": (
            "Hi {affiliate_name},\n\n"
            "We have detected unusual traffic patterns on your campaign.\n\n"
            "Please review your traffic sources immediately. Continued violation of our "
            "quality standards may result in account suspension and earnings forfeiture.\n\n"
            "Please reach out to your account manager if you have questions.\n\n"
            "Best regards,\nFraud Prevention Team"
        ),
        "tags": ["fraud", "warning", "urgent"],
    },
    {
        "name": "Performance Milestone — First Conversion",
        "category": "performance",
        "subject": "Congratulations on your first conversion!",
        "body": (
            "Hi {affiliate_name},\n\n"
            "Congratulations! You've just earned your first conversion.\n\n"
            "This is just the beginning. Keep optimizing your campaigns and the earnings will follow.\n\n"
            "Best regards,\n{manager_name}"
        ),
        "tags": ["milestone", "performance"],
    },
    {
        "name": "Weekly Performance Review",
        "category": "performance",
        "subject": "Your weekly performance summary",
        "body": (
            "Hi {affiliate_name},\n\n"
            "Here is your performance summary for this week:\n\n"
            "• Clicks: {clicks}\n"
            "• Conversions: {conversions}\n"
            "• Revenue: {revenue}\n"
            "• EPC: {epc}\n\n"
            "Keep it up! Contact me if you need help optimizing.\n\n"
            "Best regards,\n{manager_name}"
        ),
        "tags": ["performance", "weekly"],
    },
    {
        "name": "System Maintenance Announcement",
        "category": "system",
        "subject": "Scheduled maintenance notice",
        "body": (
            "Dear affiliates,\n\n"
            "We will be performing scheduled maintenance on {maintenance_date} "
            "from {start_time} to {end_time} UTC.\n\n"
            "During this time, some features may be temporarily unavailable. "
            "Please plan your campaigns accordingly.\n\n"
            "We apologize for any inconvenience.\n\n"
            "Best regards,\nPlatform Team"
        ),
        "tags": ["system", "maintenance"],
    },
]


class Command(BaseCommand):
    help = "Create default CPA notification message templates."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Recreate templates even if they already exist.")

    def handle(self, *args, **options):
        from messaging.models import MessageTemplate

        created = 0
        skipped = 0

        for tpl in TEMPLATES:
            if not options["force"] and MessageTemplate.objects.filter(name=tpl["name"]).exists():
                self.stdout.write(f"  SKIP (exists): {tpl['name']}")
                skipped += 1
                continue

            MessageTemplate.objects.update_or_create(
                name=tpl["name"],
                defaults={
                    "category": tpl["category"],
                    "subject": tpl["subject"],
                    "body": tpl["body"],
                    "tags": tpl["tags"],
                    "is_active": True,
                },
            )
            self.stdout.write(self.style.SUCCESS(f"  CREATED: {tpl['name']}"))
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Created: {created}, Skipped: {skipped}"
        ))
