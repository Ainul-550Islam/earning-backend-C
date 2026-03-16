"""
Management command: check_stock
Usage: python manage.py check_stock [--fix] [--report]
"""
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Check stock levels across all active reward items. "
        "Fires low-stock alerts and optionally corrects code-based stock drift."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            default=False,
            help="Synchronise current_stock from RedemptionCode counts (code-based items only).",
        )
        parser.add_argument(
            "--report",
            action="store_true",
            default=False,
            help="Print a full stock report to stdout without making changes.",
        )
        parser.add_argument(
            "--alert",
            action="store_true",
            default=False,
            help="Re-evaluate and fire stock alerts for all items.",
        )

    def handle(self, *args, **options):
        from inventory.models import RewardItem, StockManager
        from inventory.choices import ItemStatus, StockAlertLevel
        from inventory.signals import low_stock_alert, stock_depleted

        items = (
            RewardItem.objects.filter(status=ItemStatus.ACTIVE)
            .select_related("stock_manager")
            .order_by("name")
        )

        self.stdout.write(f"Checking {items.count()} active item(s)...\n")

        report_rows = []
        alerted = 0
        corrected = 0

        for item in items.iterator():
            stock = item.current_stock
            unlimited = item.is_unlimited

            row = {
                "name": item.name,
                "stock": "∞" if unlimited else stock,
                "alert": "—",
            }

            if options["alert"] or options["report"]:
                try:
                    sm = item.stock_manager
                    level = sm.evaluate_alert_level()
                    row["alert"] = level
                    if options["alert"] and level != StockAlertLevel.NONE:
                        changed = sm.update_alert_level()
                        if changed:
                            low_stock_alert.send(
                                sender=RewardItem, instance=item, alert_level=level
                            )
                            alerted += 1
                        if level == StockAlertLevel.DEPLETED:
                            stock_depleted.send(sender=RewardItem, instance=item)
                except StockManager.DoesNotExist:
                    row["alert"] = "no StockManager"

            if options["fix"] and not unlimited:
                from inventory.tasks import sync_stock_counts
                pass  # delegate to task for atomicity

            report_rows.append(row)

        if options["fix"]:
            from inventory.tasks import sync_stock_counts
            result = sync_stock_counts.apply().get()
            corrected = result.get("corrections", 0)
            self.stdout.write(self.style.SUCCESS(f"Corrected {corrected} stock discrepancy(ies)."))

        if options["report"]:
            self.stdout.write(f"\n{'Item':<40} {'Stock':>10} {'Alert':>15}")
            self.stdout.write("-" * 67)
            for row in report_rows:
                self.stdout.write(f"{row['name']:<40} {str(row['stock']):>10} {str(row['alert']):>15}")

        if options["alert"]:
            self.stdout.write(self.style.SUCCESS(f"Fired {alerted} stock alert(s)."))

        self.stdout.write(self.style.SUCCESS("\nStock check complete."))
