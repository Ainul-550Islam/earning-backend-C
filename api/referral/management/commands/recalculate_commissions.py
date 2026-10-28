# api/referral/management/commands/recalculate_commissions.py
# Usage: python manage.py recalculate_commissions [--user-id 123] [--days 30]

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from decimal import Decimal


class Command(BaseCommand):
    help = 'Recalculate and fix missing commissions from ReferralEarning records'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, default=None)
        parser.add_argument('--days', type=int, default=30,
                            help='Look back N days (default: 30)')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--release-held', action='store_true',
                            help='Release all expired held commissions')

    def handle(self, *args, **options):
        from api.referral.services.CommissionService import CommissionService
        from api.referral.models import CommissionHold

        dry_run = options.get('dry_run', False)

        if options.get('release_held'):
            self.stdout.write('Releasing expired held commissions...')
            result = CommissionService.release_expired_holds(dry_run=dry_run)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Released: {result["released"]}, '
                    f'Amount: ৳{result["total_amount"]}, '
                    f'Errors: {result["errors"]}'
                    + (' [DRY RUN]' if dry_run else '')
                )
            )
            return

        from datetime import timedelta
        from api.referral.models import ReferralEarning, CommissionLog

        days = options.get('days', 30)
        cutoff = timezone.now() - timedelta(days=days)

        # Find earnings without commission logs
        earnings = ReferralEarning.objects.filter(
            created_at__gte=cutoff,
        )

        if options.get('user_id'):
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=options['user_id'])
                earnings = earnings.filter(referrer=user)
            except User.DoesNotExist:
                raise CommandError(f'User id={options["user_id"]} not found')

        self.stdout.write(
            f'Checking {earnings.count()} earnings from last {days} days...'
        )

        fixed = 0
        skipped = 0

        for earning in earnings.select_related('referrer', 'referred_user'):
            # Check if CommissionLog exists
            exists = CommissionLog.objects.filter(
                user=earning.referrer,
                referred_user=earning.referred_user,
                amount=earning.amount,
                level=earning.level,
            ).exists()

            if exists:
                skipped += 1
                continue

            if not dry_run:
                CommissionLog.objects.get_or_create(
                    user=earning.referrer,
                    referred_user=earning.referred_user,
                    amount=earning.amount or Decimal('0'),
                    base_amount=earning.source_amount or Decimal('0'),
                    commission_rate=earning.commission_rate or Decimal('0'),
                    level=earning.level,
                    action_type=earning.source_type or 'task',
                    status='released',
                    source_reference=f"{earning.source_type}:{earning.source_id}" if earning.source_id else earning.source_type,
                )
                fixed += 1
            else:
                fixed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done: {fixed} fixed, {skipped} already OK'
                + (' [DRY RUN]' if dry_run else '')
            )
        )