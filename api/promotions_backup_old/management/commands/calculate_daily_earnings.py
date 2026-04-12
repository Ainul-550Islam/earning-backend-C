from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging
logger = logging.getLogger('management.daily_earnings')

class Command(BaseCommand):
    help = 'Calculate and archive daily earnings summary'

    def handle(self, *args, **options):
        from api.promotions.auditing.report_archiver import ReportArchiver
        from api.promotions.reporting.revenue_report import RevenueReport
        from api.promotions.monitoring.slack_notifier import SlackNotifier

        yesterday = timezone.now().date() - timedelta(days=1)
        report    = ReportArchiver().generate_daily_report(yesterday)
        rev_data  = RevenueReport().daily(yesterday)

        self.stdout.write(self.style.SUCCESS(
            f"Daily earnings: date={yesterday} "
            f"revenue=${rev_data.get('gross_revenue_usd',0):.2f} "
            f"submissions={rev_data.get('total_submissions',0)}"
        ))
        SlackNotifier().notify_daily_report(rev_data)
        logger.info(f'Daily earnings calculated: {yesterday} revenue=${rev_data.get("gross_revenue_usd",0):.2f}')
