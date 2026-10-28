# api/support/management/commands/seed_canned_responses.py
"""Seed default canned responses for agents."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed default canned responses for support agents'

    def handle(self, *args, **options):
        from api.support.models import CannedResponse

        canned = [
            {
                'shortcut': 'greet',
                'title': 'Greeting',
                'category': 'general',
                'content': 'Hello! Thank you for contacting support. How can I assist you today?',
            },
            {
                'shortcut': 'ack',
                'title': 'Acknowledgement',
                'category': 'general',
                'content': (
                    'Thank you for reaching out. I have received your request and '
                    'will investigate this for you. Please allow up to 24 hours for a response.'
                ),
            },
            {
                'shortcut': 'verify_offer',
                'title': 'Offer Verification Request',
                'category': 'coins',
                'content': (
                    'To verify your offer completion, please provide:\n'
                    '1. Offer name\n'
                    '2. Click ID (if available)\n'
                    '3. Screenshot of completion\n'
                    '4. Date/time when you completed the offer'
                ),
            },
            {
                'shortcut': 'withdraw_info',
                'title': 'Withdrawal Information Request',
                'category': 'payment',
                'content': (
                    'To investigate your withdrawal, please provide:\n'
                    '1. Transaction ID\n'
                    '2. Amount requested\n'
                    '3. Payment method (bKash/Nagad/Bank)\n'
                    '4. Account number used\n'
                    '5. Date of request'
                ),
            },
            {
                'shortcut': 'processing',
                'title': 'Processing Time Notice',
                'category': 'payment',
                'content': (
                    'Withdrawals are typically processed within 1-3 business days. '
                    'If it has been longer, please reply with your transaction ID '
                    'and we will investigate further.'
                ),
            },
            {
                'shortcut': 'kyc_docs',
                'title': 'KYC Documents Required',
                'category': 'kyc',
                'content': (
                    'For KYC verification, please submit:\n'
                    '1. Government-issued photo ID (NID/Passport/Driver License)\n'
                    '2. Selfie holding the ID\n'
                    '3. Ensure the photo is clear, unblurred, and all text is readable'
                ),
            },
            {
                'shortcut': 'resolve',
                'title': 'Issue Resolved',
                'category': 'general',
                'content': (
                    'I am glad to inform you that your issue has been resolved. '
                    'If you experience any further problems, please do not hesitate to contact us again. '
                    'Have a great day!'
                ),
            },
            {
                'shortcut': 'escalate',
                'title': 'Escalation Notice',
                'category': 'general',
                'content': (
                    'Your case has been escalated to our senior team for review. '
                    'You will receive an update within 24-48 hours. '
                    'We apologize for any inconvenience.'
                ),
            },
            {
                'shortcut': 'fraud_report',
                'title': 'Fraud Report Acknowledgement',
                'category': 'fraud',
                'content': (
                    'Thank you for reporting this security concern. '
                    'Our security team has been notified and will investigate immediately. '
                    'Please do not share your account details with anyone.'
                ),
            },
            {
                'shortcut': 'close_ticket',
                'title': 'Close Ticket Notice',
                'category': 'general',
                'content': (
                    'As we have not heard from you in a while, we will be closing this ticket. '
                    'If you need further assistance, please create a new ticket and we will be happy to help.'
                ),
            },
        ]

        created = 0
        for item in canned:
            obj, c = CannedResponse.objects.get_or_create(
                shortcut=item['shortcut'],
                defaults={**item, 'is_active': True}
            )
            if c:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: /{obj.shortcut} — {obj.title}"))
            else:
                self.stdout.write(f"  Exists: /{obj.shortcut}")

        self.stdout.write(self.style.SUCCESS(f"Done: {created} canned responses created"))