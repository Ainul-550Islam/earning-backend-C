from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta

from api.postback.services import PostbackInsightService
from api.postback.models import NetworkPostbackConfig


class Command(BaseCommand):
    help = 'Aggregate postback insights for analytics and anomaly detection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            help='Network key to process (optional, processes all if not provided)'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Date to process in YYYY-MM-DD format (default: yesterday)'
        )
        parser.add_argument(
            '--backfill',
            type=int,
            help='Backfill insights for the last N days'
        )
        parser.add_argument(
            '--detect-anomalies',
            action='store_true',
            help='Run anomaly detection after aggregation'
        )
        parser.add_argument(
            '--force-recalculate',
            action='store_true',
            help='Force recalculation instead of incremental update'
        )

    def handle(self, *args, **options):
        # Determine target date
        if options['date']:
            target_date = date.fromisoformat(options['date'])
        else:
            target_date = timezone.now().date() - timedelta(days=1)

        # Get networks to process
        if options['network']:
            try:
                networks = [NetworkPostbackConfig.objects.get(network_key=options['network'])]
            except NetworkPostbackConfig.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Network '{options['network']}' not found")
                )
                return
        else:
            networks = NetworkPostbackConfig.objects.all()

        self.stdout.write(f"Processing insights for {len(networks)} network(s) on {target_date}")

        total_processed = 0
        total_anomalies = 0

        for network in networks:
            self.stdout.write(f"  Processing network: {network.network_key}")

            try:
                if options['backfill']:
                    # Backfill mode
                    processed = PostbackInsightService.backfill_missing_insights(
                        network,
                        target_date - timedelta(days=options['backfill']-1),
                        target_date
                    )
                    total_processed += processed
                    self.stdout.write(f"    Backfilled {processed} days")

                elif options['force_recalculate']:
                    # Force recalculation
                    insight = PostbackInsightService.recalculate_daily_insight(network, target_date)
                    total_processed += 1
                    self.stdout.write(f"    Recalculated: {insight.received_count} received")

                else:
                    # Normal aggregation (incremental)
                    insight = PostbackInsightService.get_daily_insight(network, target_date)
                    total_processed += 1
                    self.stdout.write(f"    Aggregated: {insight.received_count} received")

                # Anomaly detection
                if options['detect_anomalies']:
                    anomalies = PostbackInsightService.detect_anomalies(network, target_date)
                    if anomalies:
                        total_anomalies += 1
                        self.stdout.write(
                            self.style.WARNING(f"    Anomalies detected: {list(anomalies.keys())}")
                        )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"    Error processing {network.network_key}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {total_processed} insights processed, "
                f"{total_anomalies} networks with anomalies"
            )
        )
