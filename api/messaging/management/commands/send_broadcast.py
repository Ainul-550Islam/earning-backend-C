"""
Management Command: send_broadcast — Trigger broadcast sending from CLI.
"""
from __future__ import annotations
import logging
from django.core.management.base import BaseCommand, CommandError
from api.messaging.exceptions import BroadcastNotFoundError, BroadcastStateError, BroadcastSendError
from api.messaging import services

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send an AdminBroadcast by its UUID."

    def add_arguments(self, parser):
        parser.add_argument("broadcast_id", type=str, help="UUID of the AdminBroadcast.")
        parser.add_argument("--async", dest="async_mode", action="store_true",
                            help="Queue via Celery instead of sending synchronously.")

    def handle(self, *args, **options):
        broadcast_id = options["broadcast_id"]
        async_mode = options["async_mode"]

        if not broadcast_id or not broadcast_id.strip():
            raise CommandError("broadcast_id must not be empty.")

        if async_mode:
            try:
                from api.messaging.tasks import send_broadcast_async
                task = send_broadcast_async.delay(broadcast_id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Broadcast {broadcast_id} queued. Task ID: {task.id}"
                    )
                )
            except Exception as exc:
                raise CommandError(f"Failed to queue broadcast: {exc}")
            return

        self.stdout.write(f"Sending broadcast {broadcast_id} ...")
        try:
            result = services.send_broadcast(broadcast_id=broadcast_id)
        except BroadcastNotFoundError as exc:
            raise CommandError(f"Not found: {exc}")
        except BroadcastStateError as exc:
            raise CommandError(f"State error: {exc}")
        except BroadcastSendError as exc:
            raise CommandError(f"Send error: {exc}")
        except Exception as exc:
            logger.exception("send_broadcast command unexpected error: %s", exc)
            raise CommandError(f"Unexpected error: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Broadcast sent: {result['delivered_count']}/{result['recipient_count']} delivered."
            )
        )
