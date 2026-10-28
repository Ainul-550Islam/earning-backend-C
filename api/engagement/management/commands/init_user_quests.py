# engagement/management/commands/init_user_quests.py
"""
Usage:
    python manage.py init_user_quests
    python manage.py init_user_quests --weekly
    python manage.py init_user_quests --user_id 5
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from engagement.services.quest_service import QuestService


class Command(BaseCommand):
    help = "Initialise daily (or weekly) quest rows for all active users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--weekly",
            action="store_true",
            help="Initialise weekly quests instead of daily.",
        )
        parser.add_argument(
            "--user_id",
            type=int,
            default=None,
            help="Only initialise for a specific user PK.",
        )

    def handle(self, *args, **options):
        User     = get_user_model()
        is_weekly = options["weekly"]
        label     = "weekly" if is_weekly else "daily"

        if options["user_id"]:
            try:
                users = [User.objects.get(pk=options["user_id"])]
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User {options['user_id']} not found."))
                return
        else:
            users = list(User.objects.filter(is_active=True))

        total = 0
        for user in users:
            try:
                tenant  = getattr(user, "tenant", None)
                created = (
                    QuestService.init_weekly(user, tenant=tenant)
                    if is_weekly
                    else QuestService.init_daily(user, tenant=tenant)
                )
                total += len(created)
            except Exception as exc:
                self.stderr.write(
                    self.style.WARNING(f"Failed for user {user.pk}: {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Initialised {label} quests: {total} new rows for {len(users)} users."
            )
        )
