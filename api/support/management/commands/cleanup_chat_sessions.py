# api/support/management/commands/cleanup_chat_sessions.py
from django.core.management.base import BaseCommand
class Command(BaseCommand):
    help = "Archive old ended chat sessions"
    def add_arguments(self, p):
        p.add_argument("--days", type=int, default=90)
    def handle(self, *args, **options):
        from api.support.tasks.chat_tasks import cleanup_old_chat_sessions
        result = cleanup_old_chat_sessions(days=options["days"])
        self.stdout.write(self.style.SUCCESS(f"Cleaned up: {result}"))