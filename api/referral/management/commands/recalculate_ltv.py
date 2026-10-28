# api/referral/management/commands/recalculate_ltv.py
# Usage: python manage.py recalculate_ltv [--user-id 123] [--all]

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Recalculate Lifetime Value (LTV) for referred users'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, dest='user_id', default=None)
        parser.add_argument('--all', action='store_true', dest='all_users')
        parser.add_argument('--batch-size', type=int, default=200, dest='batch_size')

    def handle(self, *args, **options):
        from api.referral.services.LTVService import LTVService

        start = timezone.now()

        if options.get('user_id'):
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=options['user_id'])
                result = LTVService.recalculate_all_for_referrer(user)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{user.username}: {result["updated"]} LTV records updated'
                    )
                )
            except User.DoesNotExist:
                raise CommandError(f'User id={options["user_id"]} not found')
        else:
            self.stdout.write('Recalculating all LTV records...')
            result = LTVService.recalculate_all(
                batch_size=options.get('batch_size', 200)
            )
            elapsed = (timezone.now() - start).total_seconds()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done in {elapsed:.1f}s: '
                    f'{result["updated"]} updated, '
                    f'{result["errors"]} errors'
                )
            )