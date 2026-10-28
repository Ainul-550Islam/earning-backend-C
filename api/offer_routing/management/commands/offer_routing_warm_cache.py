"""
Management command: warm_cache
Usage: python manage.py offer_routing_warm_cache [--tenant-id N]

Pre-warms the routing cache for all (or a specific) tenant so that
the first real request doesn't suffer a cold-start penalty.
"""

import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Pre-warm the routing cache for all or a specific tenant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            dest="tenant_id",
            type=int,
            default=None,
            help="Only warm cache for this tenant ID.",
        )

    def handle(self, *args, **options):
        from offer_routing.services.cache import cache_service
        from offer_routing.models import OfferRoute

        tenant_id = options.get("tenant_id")
        qs = User.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(id=tenant_id)

        total_routes = 0
        for tenant in qs:
            routes = OfferRoute.objects.filter(tenant=tenant, is_active=True)
            for route in routes:
                cache_key = f"routing:route:{route.id}:warm"
                cache_service.set(cache_key, {"route_id": route.id, "warm": True}, timeout=3600)
                total_routes += 1
            self.stdout.write(
                self.style.SUCCESS(f"Tenant {tenant.id}: {routes.count()} routes warmed")
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nDone — {total_routes} route cache entries written.")
        )
