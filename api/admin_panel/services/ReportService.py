# api/admin_panel/services/ReportService.py
"""Service for generating reports."""
import logging
logger = logging.getLogger(__name__)


class ReportService:
    @staticmethod
    def generate(report) -> bool:
        """Generate a Report object's data. Returns True on success."""
        try:
            from django.utils import timezone
            report.report_data = {
                'generated_at': timezone.now().isoformat(),
                'report_type': report.report_type,
                'rows': [],
                'summary': {},
            }
            report.status = 'completed'
            report.save(update_fields=['report_data', 'status'])
            return True
        except Exception as e:
            logger.error(f"ReportService.generate error: {e}")
            report.status = 'failed'
            report.save(update_fields=['status'])
            return False

    @staticmethod
    def get_report_data(report_type: str, filters: dict) -> dict:
        """Gather report data for a given type and filter set."""
        from django.utils import timezone
        from datetime import timedelta
        start = filters.get('start_date')
        end = filters.get('end_date', timezone.now().date())
        try:
            if report_type == 'user':
                from django.contrib.auth import get_user_model
                User = get_user_model()
                qs = User.objects.all()
                if start:
                    qs = qs.filter(date_joined__date__gte=start)
                if end:
                    qs = qs.filter(date_joined__date__lte=end)
                return {
                    'total': qs.count(),
                    'active': qs.filter(is_active=True).count(),
                    'rows': list(qs.values('id', 'username', 'email', 'date_joined', 'is_active')[:10000]),
                }
            return {'rows': [], 'total': 0}
        except Exception as e:
            logger.error(f"ReportService.get_report_data error: {e}")
            return {'rows': [], 'error': str(e)}