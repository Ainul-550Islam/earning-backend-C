"""
Management command to populate rate limit configurations.
Usage: python manage.py populate_rate_limits
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from api.tasks.models import RateLimitConfig
from api.tasks.middleware_rate_limit import DEFAULT_RATE_LIMITS


class Command(BaseCommand):
    help = 'Populate database with default rate limit configurations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing configurations to defaults',
        )

    def handle(self, *args, **options):
        self.stdout.write('Populating rate limit configurations...')

        created = 0
        updated = 0

        for limit_type, config in DEFAULT_RATE_LIMITS.items():
            # Create display name from limit type
            display_name = limit_type.replace('_', ' ').title()

            # Add descriptions
            descriptions = {
                'api_general': 'General API endpoints rate limit',
                'postback': 'Postback API calls from external sources',
                'withdrawal': 'User withdrawal requests',
                'task_click': 'Task completion clicks',
                'survey_submit': 'Survey form submissions',
                'offer_click': 'Offer wall clicks',
                'proof_submit': 'Task proof submissions'
            }

            defaults = {
                'display_name': display_name,
                'description': descriptions.get(limit_type, ''),
                'limit': config['limit'],
                'window_seconds': config['window'],
                'scope': config.get('scope', 'user'),
                'is_active': True,
                'is_default': True,
                'updated_at': timezone.now()
            }

            obj, created_flag = RateLimitConfig.objects.update_or_create(
                limit_type=limit_type,
                defaults=defaults
            )

            if created_flag:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created: {limit_type} ({config["limit"]}/{config["window"]}s)')
                )
            elif options['reset']:
                updated += 1
                self.stdout.write(
                    self.style.WARNING(f'Reset: {limit_type} ({config["limit"]}/{config["window"]}s)')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed {created + updated} rate limit configurations '
                f'({created} created, {updated} updated)'
            )
        )