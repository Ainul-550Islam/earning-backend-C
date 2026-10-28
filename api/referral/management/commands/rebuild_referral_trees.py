# api/referral/management/commands/rebuild_referral_trees.py
# Usage: python manage.py rebuild_referral_trees [--user-id 123] [--all]
# ============================================================

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Rebuild referral trees for all users or a specific user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id', type=int, dest='user_id', default=None,
            help='Rebuild tree for a specific user ID'
        )
        parser.add_argument(
            '--all', action='store_true', dest='all_users',
            help='Rebuild all trees'
        )
        parser.add_argument(
            '--batch-size', type=int, default=100, dest='batch_size',
            help='Batch size for bulk rebuild (default: 100)'
        )
        parser.add_argument(
            '--dry-run', action='store_true', dest='dry_run',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        from api.referral.services.ReferralTreeService import ReferralTreeService

        user_id = options.get('user_id')
        all_users = options.get('all_users')
        batch_size = options.get('batch_size', 100)
        dry_run = options.get('dry_run', False)

        if dry_run:
            health = ReferralTreeService.get_tree_health_check()
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] Tree health: {health}'
                )
            )
            return

        start = timezone.now()

        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                tree = ReferralTreeService.rebuild_tree(user)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Tree rebuilt for {user.username}: '
                        f'{tree.total_members} members, ৳{tree.total_earned}'
                    )
                )
            except User.DoesNotExist:
                raise CommandError(f'User with id={user_id} not found')

        elif all_users:
            self.stdout.write('Rebuilding all referral trees...')
            result = ReferralTreeService.rebuild_all_trees(
                batch_size=batch_size
            )
            elapsed = (timezone.now() - start).total_seconds()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done in {elapsed:.1f}s: '
                    f'{result["rebuilt"]} rebuilt, '
                    f'{result["errors"]} errors'
                )
            )

        else:
            # Just stale trees
            self.stdout.write('Rebuilding stale trees (7+ days)...')
            from api.referral.models import ReferralTree
            from datetime import timedelta
            stale_cutoff = timezone.now() - timedelta(days=7)
            stale = ReferralTree.objects.filter(
                last_rebuilt_at__lt=stale_cutoff
            )
            count = stale.count()
            self.stdout.write(f'Found {count} stale trees')

            rebuilt = 0
            for tree in stale:
                try:
                    ReferralTreeService.rebuild_tree(tree.root_user)
                    rebuilt += 1
                    if rebuilt % 50 == 0:
                        self.stdout.write(f'  {rebuilt}/{count} rebuilt...')
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f'Error for {tree.root_user.username}: {e}'
                        )
                    )

            elapsed = (timezone.now() - start).total_seconds()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done in {elapsed:.1f}s: {rebuilt}/{count} rebuilt'
                )
            )