# api/support/management/commands/seed_sla_policies.py
"""Seed default SLA policies."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed default SLA policies for all priority levels'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Overwrite existing policies')

    def handle(self, *args, **options):
        from api.support.models import SLAPolicy
        from api.support.choices import SLA_FIRST_RESPONSE_HOURS, SLA_RESOLUTION_HOURS

        policies = [
            {'name': 'Urgent SLA',  'priority_level': 'urgent',
             'first_response_hours': 1,  'resolution_hours': 4,  'business_hours_only': False},
            {'name': 'High SLA',    'priority_level': 'high',
             'first_response_hours': 4,  'resolution_hours': 24, 'business_hours_only': True},
            {'name': 'Medium SLA',  'priority_level': 'medium',
             'first_response_hours': 8,  'resolution_hours': 48, 'business_hours_only': True},
            {'name': 'Low SLA',     'priority_level': 'low',
             'first_response_hours': 24, 'resolution_hours': 72, 'business_hours_only': True},
        ]

        created = updated = 0
        for policy_data in policies:
            priority = policy_data['priority_level']
            existing = SLAPolicy.objects.filter(priority_level=priority).first()
            if existing and not options['force']:
                self.stdout.write(f'  Skipping {priority} (already exists)')
                continue
            obj, c = SLAPolicy.objects.update_or_create(
                priority_level=priority,
                defaults={**policy_data, 'is_active': True}
            )
            if c: created += 1
            else: updated += 1
            self.stdout.write(self.style.SUCCESS(
                f"  {'Created' if c else 'Updated'}: {obj.name} "
                f"(FR:{obj.first_response_hours}h, Res:{obj.resolution_hours}h)"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"Done: {created} created, {updated} updated"
        ))