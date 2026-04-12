"""
Management command: python manage.py send_broadcast <broadcast_id>
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send a broadcast message by ID"

    def add_arguments(self, parser):
        parser.add_argument("broadcast_id", type=str)
        parser.add_argument("--async", dest="use_async", action="store_true")

    def handle(self, *args, **options):
        broadcast_id = options["broadcast_id"]
        use_async    = options.get("use_async", False)

        if use_async:
            from messaging.tasks import send_broadcast_async
            task = send_broadcast_async.delay(broadcast_id)
            self.stdout.write(f"✅ Queued broadcast {broadcast_id} — task: {task.id}")
        else:
            from messaging import services
            try:
                result = services.send_broadcast(broadcast_id=broadcast_id)
                self.stdout.write(self.style.SUCCESS(
                    f"✅ Sent to {result['delivered']} recipients."
                ))
            except Exception as exc:
                self.stderr.write(f"❌ Failed: {exc}")
