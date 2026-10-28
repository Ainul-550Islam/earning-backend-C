# api/support/management/commands/seed_departments.py
"""Seed default support departments."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed default support departments'

    def handle(self, *args, **options):
        from api.support.models import Department

        departments = [
            {'name': 'General Support',    'slug': 'general',    'routing_rule': 'least_busy',  'auto_assign': True},
            {'name': 'Payment Support',     'slug': 'payment',    'routing_rule': 'skill_match', 'auto_assign': True},
            {'name': 'Technical Support',   'slug': 'technical',  'routing_rule': 'least_busy',  'auto_assign': True},
            {'name': 'Account Management',  'slug': 'account',    'routing_rule': 'round_robin', 'auto_assign': True},
            {'name': 'Fraud & Security',    'slug': 'fraud',      'routing_rule': 'skill_match', 'auto_assign': False},
            {'name': 'KYC Verification',    'slug': 'kyc',        'routing_rule': 'skill_match', 'auto_assign': False},
            {'name': 'CPA Disputes',        'slug': 'disputes',   'routing_rule': 'least_busy',  'auto_assign': True},
            {'name': 'VIP Support',         'slug': 'vip',        'routing_rule': 'skill_match', 'auto_assign': False},
        ]

        created = 0
        for dept_data in departments:
            obj, c = Department.objects.get_or_create(
                slug=dept_data['slug'],
                defaults={**dept_data, 'is_active': True}
            )
            if c:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {obj.name}"))
            else:
                self.stdout.write(f"  Exists: {obj.name}")

        self.stdout.write(self.style.SUCCESS(f"Done: {created} departments created"))