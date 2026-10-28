# engagement/management/commands/engagement_setup.py
"""
One-shot setup command — runs ALL seed commands in correct order.
Usage:
    python manage.py engagement_setup
    python manage.py engagement_setup --clear
"""
from django.core.management.base import BaseCommand
from django.core import management


class Command(BaseCommand):
    help = "Run all engagement seed commands (core + advanced) in the correct order."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true",
                            help="Pass --clear to each seed command.")

    def handle(self, *args, **options):
        clear = options["clear"]
        self.stdout.write(self.style.MIGRATE_HEADING("\n🚀 Running FULL engagement setup…\n"))

        steps = [
            # Core
            ("seed_achievements",        {"clear": clear}),
            ("seed_leaderboard_rewards", {"clear": clear}),
            ("seed_quests",              {"clear": clear}),
            ("seed_shop",                {"clear": clear}),
            # Advanced
            ("seed_advanced",            {"clear": clear}),
            ("seed_battle_pass",         {"clear": clear}),
        ]

        for cmd_name, kwargs in steps:
            self.stdout.write(f"  → {cmd_name}…")
            try:
                management.call_command(cmd_name, **kwargs, stdout=self.stdout)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  ✘ {cmd_name} failed: {exc}"))
                raise

        self.stdout.write(self.style.SUCCESS("\n✅ Full engagement setup complete!\n"))
        self.stdout.write("Next steps:")
        self.stdout.write("  python manage.py migrate")
        self.stdout.write("  Add engagement.urls to root urls.py")
        self.stdout.write("  Add CELERY_BEAT_SCHEDULE from engagement/celery_beat.py")
        self.stdout.write("  Set FIREBASE_CREDENTIALS_PATH for push notifications")
