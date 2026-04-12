"""Performance Metric model helpers and trend analysis."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class PerformanceMetricManager(models.Manager):
    def for_engine(self, engine_name: str, hours: int = 24):
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(
            engine_name=engine_name,
            recorded_at__gte=since
        ).order_by('-recorded_at')

    def avg_latency(self, engine_name: str, hours: int = 1) -> float:
        from django.db.models import Avg
        since = timezone.now() - timedelta(hours=hours)
        result = self.filter(
            engine_name=engine_name,
            metric_type='detection_latency',
            recorded_at__gte=since,
        ).aggregate(avg=Avg('value'))
        return round(result['avg'] or 0.0, 2)

    def p95_latency(self, engine_name: str, hours: int = 1) -> float:
        """Approximate 95th percentile latency."""
        since   = timezone.now() - timedelta(hours=hours)
        values  = list(
            self.filter(
                engine_name=engine_name,
                metric_type='detection_latency',
                recorded_at__gte=since,
            ).values_list('value', flat=True).order_by('value')
        )
        if not values:
            return 0.0
        p95_idx = int(len(values) * 0.95)
        return round(values[min(p95_idx, len(values) - 1)], 2)

    def dashboard(self) -> dict:
        from django.db.models import Avg, Max
        engines = self.values_list('engine_name', flat=True).distinct()
        result  = {}
        for engine in engines:
            result[engine] = {
                'avg_latency_ms': self.avg_latency(engine),
                'p95_latency_ms': self.p95_latency(engine),
                'max_latency_ms': round(
                    self.for_engine(engine, 1)
                    .aggregate(m=Max('value'))['m'] or 0.0, 2
                ),
                'sample_count': self.for_engine(engine, 1).count(),
            }
        return result

    def cleanup_old(self, days: int = 90) -> int:
        cutoff   = timezone.now() - timedelta(days=days)
        deleted, _ = self.filter(recorded_at__lt=cutoff).delete()
        return deleted

    def trend(self, engine_name: str, hours: int = 24) -> list:
        """Hourly average latency trend."""
        from django.db.models.functions import TruncHour
        from django.db.models import Avg
        since = timezone.now() - timedelta(hours=hours)
        return list(
            self.filter(engine_name=engine_name, recorded_at__gte=since,
                        metric_type='detection_latency')
            .annotate(hour=TruncHour('recorded_at'))
            .values('hour')
            .annotate(avg_ms=Avg('value'))
            .order_by('hour')
        )
