# api/admin_panel/management/commands/seed_email_templates.py
"""Seed default email templates for the earning platform."""
from django.core.management.base import BaseCommand

TEMPLATES = [
    {
        'key': 'welcome_email',
        'name': 'Welcome Email',
        'subject': 'Welcome to {{site_name}}, {{user_name}}!',
        'body_html': '<h1>Welcome {{user_name}}!</h1><p>You have {{welcome_bonus}} bonus points. Start earning now!</p>',
        'body_text': 'Welcome {{user_name}}!\n\nYou have {{welcome_bonus}} bonus points. Start earning now!',
        'variables': ['user_name', 'site_name', 'welcome_bonus'],
    },
    {
        'key': 'withdrawal_approved',
        'name': 'Withdrawal Approved',
        'subject': 'Your withdrawal of {{amount}} has been approved!',
        'body_html': '<h2>Withdrawal Approved</h2><p>{{user_name}}, your withdrawal of <b>{{amount}}</b> via {{method}} has been approved.</p>',
        'body_text': 'Hi {{user_name}},\n\nYour withdrawal of {{amount}} via {{method}} has been approved.\n\nExpected: {{expected_time}}',
        'variables': ['user_name', 'amount', 'method', 'expected_time'],
    },
    {
        'key': 'withdrawal_rejected',
        'name': 'Withdrawal Rejected',
        'subject': 'Your withdrawal request was rejected',
        'body_html': '<h2>Withdrawal Rejected</h2><p>{{user_name}}, your withdrawal of {{amount}} was rejected.</p><p>Reason: {{reason}}</p>',
        'body_text': 'Hi {{user_name}},\n\nYour withdrawal of {{amount}} was rejected.\nReason: {{reason}}',
        'variables': ['user_name', 'amount', 'reason'],
    },
    {
        'key': 'referral_bonus',
        'name': 'Referral Bonus',
        'subject': 'You earned {{bonus_points}} bonus points from a referral!',
        'body_html': '<h2>Referral Bonus!</h2><p>{{user_name}}, you earned {{bonus_points}} points because {{referred_user}} joined using your link!</p>',
        'body_text': 'Hi {{user_name}},\n\nYou earned {{bonus_points}} points! {{referred_user}} joined using your referral link.',
        'variables': ['user_name', 'bonus_points', 'referred_user'],
    },
    {
        'key': 'report_ready',
        'name': 'Report Ready',
        'subject': 'Your report "{{report_name}}" is ready',
        'body_html': '<p>Hi {{user_name}},</p><p>Your report <b>{{report_name}}</b> is ready. {{row_count}} rows in {{format}} format.</p><p><a href="{{download_url}}">Download Report</a></p>',
        'body_text': 'Hi {{user_name}},\n\nYour report "{{report_name}}" is ready.\nRows: {{row_count}} | Format: {{format}}\nDownload: {{download_url}}\n\nLink expires in 7 days.',
        'variables': ['user_name', 'report_name', 'row_count', 'format', 'download_url'],
    },
    {
        'key': 'security_alert',
        'name': 'Security Alert',
        'subject': 'Security Alert: New login detected on your account',
        'body_html': '<h2>Security Alert</h2><p>{{user_name}}, a new login was detected from {{ip_address}} at {{login_time}}.</p><p>If this was not you, please change your password immediately.</p>',
        'body_text': 'Hi {{user_name}},\n\nNew login detected from {{ip_address}} at {{login_time}}.\nIf this was not you, change your password immediately.',
        'variables': ['user_name', 'ip_address', 'login_time', 'device'],
    },
    {
        'key': 'otp_verification',
        'name': 'OTP Verification',
        'subject': 'Your {{site_name}} verification code: {{otp}}',
        'body_html': '<h2>Verification Code</h2><p>Your OTP is: <b style="font-size:24px;">{{otp}}</b></p><p>Expires in {{expiry_minutes}} minutes.</p>',
        'body_text': 'Your verification code: {{otp}}\n\nExpires in {{expiry_minutes}} minutes. Do not share this code.',
        'variables': ['user_name', 'otp', 'site_name', 'expiry_minutes'],
    },
]


class Command(BaseCommand):
    help = 'Seed default email templates.'

    def add_arguments(self, parser):
        parser.add_argument('--overwrite', action='store_true')

    def handle(self, *args, **options):
        from api.admin_panel.models.config import EmailTemplate
        overwrite = options['overwrite']
        created = updated = skipped = 0

        for tmpl in TEMPLATES:
            exists = EmailTemplate.objects.filter(key=tmpl['key']).exists()
            if exists and not overwrite:
                skipped += 1
                self.stdout.write(f'  SKIP: {tmpl["key"]}')
                continue
            obj, was_created = EmailTemplate.objects.update_or_create(
                key=tmpl['key'],
                defaults={
                    'name': tmpl['name'],
                    'subject': tmpl['subject'],
                    'body_html': tmpl['body_html'],
                    'body_text': tmpl['body_text'],
                    'variables': tmpl['variables'],
                    'is_active': True,
                }
            )
            if was_created:
                created += 1
                self.stdout.write(f'  Created: {tmpl["key"]}')
            else:
                updated += 1
                self.stdout.write(f'  Updated: {tmpl["key"]}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Created: {created}, Updated: {updated}, Skipped: {skipped}'
        ))