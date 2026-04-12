"""
Management command: cleanup_messaging
Run all messaging cleanup tasks manually.
Usage: python manage.py cleanup_messaging --all
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run messaging cleanup tasks."

    def add_arguments(self, parser):
        parser.add_argument("--all",          action="store_true", help="Run all cleanup tasks")
        parser.add_argument("--inbox",        action="store_true", help="Clean old inbox items")
        parser.add_argument("--stories",      action="store_true", help="Clean old stories")
        parser.add_argument("--calls",        action="store_true", help="Clean old call sessions")
        parser.add_argument("--edit-history", action="store_true", help="Clean old edit history")
        parser.add_argument("--presence",     action="store_true", help="Mark offline presence")
        parser.add_argument("--disappearing", action="store_true", help="Expire disappearing messages")
        parser.add_argument("--days", type=int, default=90, help="Retention days")

    def handle(self, *args, **options):
        run_all = options["all"]

        if run_all or options["inbox"]:
            from messaging.tasks import cleanup_old_inbox_items
            r = cleanup_old_inbox_items(days=options["days"])
            self.stdout.write(self.style.SUCCESS(f"Inbox cleanup: {r}"))

        if run_all or options["stories"]:
            from messaging.tasks import cleanup_old_stories, expire_stories_task
            r1 = expire_stories_task()
            r2 = cleanup_old_stories(days=7)
            self.stdout.write(self.style.SUCCESS(f"Stories: expired={r1} cleaned={r2}"))

        if run_all or options["calls"]:
            from messaging.tasks import cleanup_old_call_sessions, expire_calls
            r1 = expire_calls()
            r2 = cleanup_old_call_sessions(days=30)
            self.stdout.write(self.style.SUCCESS(f"Calls: expired={r1} cleaned={r2}"))

        if run_all or options["edit_history"]:
            from messaging.tasks import cleanup_old_edit_history
            r = cleanup_old_edit_history(days=365)
            self.stdout.write(self.style.SUCCESS(f"Edit history: {r}"))

        if run_all or options["presence"]:
            from messaging.tasks import cleanup_presence
            r = cleanup_presence()
            self.stdout.write(self.style.SUCCESS(f"Presence: {r}"))

        if run_all or options["disappearing"]:
            from messaging.tasks import expire_disappearing_messages_task
            r = expire_disappearing_messages_task()
            self.stdout.write(self.style.SUCCESS(f"Disappearing: {r}"))
