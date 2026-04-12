# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Management Command
seed_webhook_toggles: Register all api.webhooks endpoints in the
EndpointToggle system so they can be enabled/disabled from the admin panel.

Usage:
    python manage.py seed_webhook_toggles
    python manage.py seed_webhook_toggles --disable  # create as disabled
"""

from django.core.management.base import BaseCommand

WEBHOOK_ENDPOINTS = [
    # label, path, method, group
    ("Webhook: List Endpoints",           "/api/webhooks/endpoints/",                       "GET",    "webhooks"),
    ("Webhook: Create Endpoint",          "/api/webhooks/endpoints/",                       "POST",   "webhooks"),
    ("Webhook: Retrieve Endpoint",        "/api/webhooks/endpoints/{id}/",                  "GET",    "webhooks"),
    ("Webhook: Update Endpoint",          "/api/webhooks/endpoints/{id}/",                  "PATCH",  "webhooks"),
    ("Webhook: Delete Endpoint",          "/api/webhooks/endpoints/{id}/",                  "DELETE", "webhooks"),
    ("Webhook: Rotate Secret",            "/api/webhooks/endpoints/{id}/rotate-secret/",    "POST",   "webhooks"),
    ("Webhook: Test Ping",                "/api/webhooks/endpoints/{id}/test/",             "POST",   "webhooks"),
    ("Webhook: Pause Endpoint",           "/api/webhooks/endpoints/{id}/pause/",            "PATCH",  "webhooks"),
    ("Webhook: Resume Endpoint",          "/api/webhooks/endpoints/{id}/resume/",           "PATCH",  "webhooks"),
    ("Webhook: List Subscriptions",       "/api/webhooks/endpoints/{id}/subscriptions/",   "GET",    "webhooks"),
    ("Webhook: Create Subscription",      "/api/webhooks/endpoints/{id}/subscriptions/",   "POST",   "webhooks"),
    ("Webhook: Update Subscription",      "/api/webhooks/endpoints/{id}/subscriptions/{id}/", "PATCH", "webhooks"),
    ("Webhook: Delete Subscription",      "/api/webhooks/endpoints/{id}/subscriptions/{id}/", "DELETE","webhooks"),
    ("Webhook: List Delivery Logs",       "/api/webhooks/logs/",                            "GET",    "webhooks"),
    ("Webhook: Retrieve Delivery Log",    "/api/webhooks/logs/{id}/",                       "GET",    "webhooks"),
    ("Webhook: Retry Delivery",           "/api/webhooks/logs/{id}/retry/",                 "POST",   "webhooks"),
    ("Webhook: Emit Event (Staff Only)",  "/api/webhooks/emit/",                            "POST",   "webhooks_admin"),
    ("Webhook: List Event Types",         "/api/webhooks/event-types/",                     "GET",    "webhooks"),
]


class Command(BaseCommand):
    help = (
        "Ainul Enterprise Engine — Seed EndpointToggle records "
        "for all api.webhooks routes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--disable",
            action="store_true",
            help="Create toggles in disabled state (default: enabled).",
        )

    def handle(self, *args, **options):
        from api.admin_panel.endpoint_toggle import EndpointToggle

        is_enabled = not options["disable"]
        created_count = 0
        updated_count = 0

        for label, path, method, group in WEBHOOK_ENDPOINTS:
            toggle, created = EndpointToggle.objects.get_or_create(
                path=path,
                method=method,
                defaults={
                    "label":      label,
                    "group":      group,
                    "is_enabled": is_enabled,
                    "disabled_message": (
                        "Webhook service is temporarily unavailable. "
                        "Contact Ainul Enterprise support."
                    ),
                },
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ Created: [{method}] {path}")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"  ↩  Exists : [{method}] {path}")
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done — Created: {created_count}, Already existed: {updated_count}"
            )
        )
        self.stdout.write(
            "Run 'python manage.py seed_webhook_toggles --disable' "
            "to register them as disabled."
        )
