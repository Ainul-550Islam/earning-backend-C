from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging
logger = logging.getLogger('management.daily_report')

class Command(BaseCommand):
    help = 'Send daily business report to admins and Slack'

    def handle(self, *args, **options):
        from api.promotions.reporting.revenue_report import RevenueReport
        from api.promotions.reporting.fraud_analytics import FraudAnalyticsReport
        from api.promotions.reporting.user_growth_stats import UserGrowthStats
        from api.promotions.monitoring.slack_notifier import SlackNotifier
        from django.core.mail import send_mail
        from django.conf import settings

        yesterday = timezone.now().date() - timedelta(days=1)
        report    = {
            'date':    str(yesterday),
            'revenue': RevenueReport().daily(yesterday),
            'fraud':   FraudAnalyticsReport().summary(days=1),
            'users':   UserGrowthStats().overview(days=1),
        }
        # Slack
        SlackNotifier().notify_daily_report(report['revenue'])
        # Email
        admins = getattr(settings, 'ADMIN_EMAILS', [])
        if admins:
            send_mail(f'Daily Report — {yesterday}', str(report), None, admins, fail_silently=True)
        self.stdout.write(self.style.SUCCESS(f'Daily report sent for {yesterday}'))
