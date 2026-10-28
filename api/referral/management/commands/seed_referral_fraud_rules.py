# api/referral/management/commands/seed_referral_fraud_rules.py
# Usage: python manage.py seed_referral_fraud_rules
# Seeds default fraud detection rules if they don't exist

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed default fraud detection rules'

    DEFAULT_RULES = [
        {
            'rule_type': 'self_refer',
            'name': 'Self-Referral Block',
            'action': 'block',
            'fraud_score_points': 100,
            'priority': 100,
            'description': 'User cannot refer themselves',
        },
        {
            'rule_type': 'ip_match',
            'name': 'Same IP Address',
            'action': 'hold_commission',
            'fraud_score_points': 40,
            'priority': 80,
            'description': 'Referrer and referred user from same IP',
        },
        {
            'rule_type': 'ip_subnet_match',
            'name': 'Same Subnet',
            'action': 'flag',
            'fraud_score_points': 20,
            'priority': 60,
            'description': 'Same /24 subnet (same network)',
        },
        {
            'rule_type': 'email_domain',
            'name': 'Disposable Email',
            'action': 'hold_commission',
            'fraud_score_points': 30,
            'priority': 70,
            'description': 'Referred user using disposable email domain',
        },
        {
            'rule_type': 'velocity',
            'name': 'High Velocity',
            'action': 'flag',
            'threshold': 20,
            'time_window_minutes': 60,
            'fraud_score_points': 25,
            'priority': 75,
            'description': 'More than 20 referrals per hour',
        },
        {
            'rule_type': 'new_account',
            'name': 'Brand New Account',
            'action': 'flag',
            'fraud_score_points': 15,
            'priority': 50,
            'description': 'Referred user account less than 1 hour old',
        },
        {
            'rule_type': 'blacklisted',
            'name': 'Blacklisted Pattern',
            'action': 'block',
            'fraud_score_points': 100,
            'priority': 90,
            'description': 'Matches blacklist entry (IP/email/device)',
        },
        {
            'rule_type': 'device_match',
            'name': 'Same Device',
            'action': 'hold_commission',
            'fraud_score_points': 35,
            'priority': 65,
            'description': 'Same device fingerprint as referrer',
        },
    ]

    def handle(self, *args, **options):
        from api.referral.models import ReferralFraudRule

        created = 0
        skipped = 0

        for rule_data in self.DEFAULT_RULES:
            _, was_created = ReferralFraudRule.objects.get_or_create(
                rule_type=rule_data['rule_type'],
                defaults={
                    'name': rule_data.get('name', ''),
                    'description': rule_data.get('description', ''),
                    'action': rule_data.get('action', 'flag'),
                    'threshold': rule_data.get('threshold', 0),
                    'time_window_minutes': rule_data.get('time_window_minutes', 60),
                    'fraud_score_points': rule_data.get('fraud_score_points', 10),
                    'priority': rule_data.get('priority', 0),
                    'is_active': True,
                }
            )
            if was_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  Created: {rule_data["rule_type"]}')
                )
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone: {created} rules created, {skipped} already existed'
            )
        )