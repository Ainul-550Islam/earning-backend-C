"""
Management command: seed_telemetry
Creates realistic sample data for development and demos.

Usage:
  python manage.py seed_telemetry
  python manage.py seed_telemetry --metrics 200 --logs 500
  python manage.py seed_telemetry --clear
"""
import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


SERVICES     = ['api-gateway', 'auth-service', 'payment-service', 'user-service', 'notification-service']
ENVIRONMENTS = ['production', 'staging', 'development']
LOG_LEVELS   = ['debug', 'info', 'warning', 'error', 'critical']
ALERT_TYPES  = ['metric', 'log', 'health']
SEVERITIES   = ['info', 'warning', 'error', 'critical']


class Command(BaseCommand):
    help = 'Seed the database with realistic telemetry sample data.'

    def add_arguments(self, parser):
        parser.add_argument('--metrics',  type=int, default=100)
        parser.add_argument('--logs',     type=int, default=200)
        parser.add_argument('--traces',   type=int, default=50)
        parser.add_argument('--alerts',   type=int, default=20)
        parser.add_argument('--health',   type=int, default=10)
        parser.add_argument('--clear',    action='store_true',
                            help='Clear existing telemetry data before seeding.')

    def handle(self, *args, **options):
        if options['clear']:
            self._clear_data()

        self._seed_metrics(options['metrics'])
        self._seed_logs(options['logs'])
        self._seed_traces(options['traces'])
        self._seed_alerts(options['alerts'])
        self._seed_health(options['health'])

        self.stdout.write(self.style.SUCCESS('\nSeeding complete!'))

    def _clear_data(self):
        from api.telemetry_observability.models.metric_event  import MetricEvent
        from api.telemetry_observability.models.log_entry     import LogEntry
        from api.telemetry_observability.models.trace_span    import TraceSpan
        from api.telemetry_observability.models.alert         import Alert
        from api.telemetry_observability.models.health_status import HealthStatus

        for model in (MetricEvent, LogEntry, TraceSpan, Alert, HealthStatus):
            count = model.objects.all().delete()[0]
            self.stdout.write(f'Cleared {count} {model.__name__} records.')

    def _seed_metrics(self, n):
        from api.telemetry_observability.models.metric_event import MetricEvent
        metric_names = ['cpu_usage', 'memory_usage', 'request_count',
                        'error_rate', 'response_time_ms', 'db_connections']
        now   = timezone.now()
        batch = []
        for i in range(n):
            batch.append(MetricEvent(
                name        = random.choice(metric_names),
                metric_type = random.choice(['counter', 'gauge', 'histogram']),
                value       = round(random.uniform(0, 100), 2),
                unit        = random.choice(['ms', '%', 'count', 'bytes']),
                service     = random.choice(SERVICES),
                environment = random.choice(ENVIRONMENTS),
                source      = 'seed',
                labels      = {'region': random.choice(['us-east-1', 'eu-west-1'])},
                timestamp   = now - timedelta(minutes=random.randint(0, 1440)),
            ))
        MetricEvent.objects.bulk_create(batch)
        self.stdout.write(f'Created {n} metrics.')

    def _seed_logs(self, n):
        from api.telemetry_observability.models.log_entry import LogEntry
        messages = [
            'Request processed successfully', 'Database query timeout',
            'Cache miss for key {key}', 'User authentication failed',
            'Payment processed', 'Email notification sent',
            'Rate limit exceeded', 'Service health check passed',
        ]
        now   = timezone.now()
        batch = []
        for i in range(n):
            level = random.choices(LOG_LEVELS, weights=[10, 50, 20, 15, 5])[0]
            batch.append(LogEntry(
                level       = level,
                message     = random.choice(messages),
                logger_name = 'app.service',
                source      = 'seed',
                service     = random.choice(SERVICES),
                environment = random.choice(ENVIRONMENTS),
                context     = {'request_id': str(uuid.uuid4())},
                tags        = [random.choice(SERVICES)],
                timestamp   = now - timedelta(minutes=random.randint(0, 1440)),
            ))
        LogEntry.objects.bulk_create(batch)
        self.stdout.write(f'Created {n} log entries.')

    def _seed_traces(self, n):
        from api.telemetry_observability.models.trace_span import TraceSpan
        operations = ['GET /api/users', 'POST /api/payments', 'db.query',
                      'cache.get', 'POST /api/auth/login', 'GET /api/metrics']
        now   = timezone.now()
        batch = []
        for i in range(n):
            start = now - timedelta(minutes=random.randint(0, 1440))
            dur   = random.uniform(10, 5000)
            batch.append(TraceSpan(
                trace_id       = str(uuid.uuid4()),
                span_id        = str(uuid.uuid4()),
                operation_name = random.choice(operations),
                service        = random.choice(SERVICES),
                start_time     = start,
                end_time       = start + timedelta(milliseconds=dur),
                duration_ms    = round(dur, 2),
                status         = random.choices(['success', 'error', 'timeout'],
                                                weights=[80, 15, 5])[0],
                tags           = {'env': random.choice(ENVIRONMENTS)},
            ))
        TraceSpan.objects.bulk_create(batch)
        self.stdout.write(f'Created {n} trace spans.')

    def _seed_alerts(self, n):
        from api.telemetry_observability.models.alert import Alert
        now   = timezone.now()
        batch = []
        for i in range(n):
            sev    = random.choices(SEVERITIES, weights=[20, 40, 25, 15])[0]
            status = random.choices(['open', 'acknowledged', 'resolved'],
                                    weights=[40, 20, 40])[0]
            batch.append(Alert(
                name        = f'alert-{i+1}-{sev}',
                alert_type  = random.choice(ALERT_TYPES),
                severity    = sev,
                status      = status,
                message     = f'Sample {sev} alert for testing',
                service     = random.choice(SERVICES),
                environment = random.choice(ENVIRONMENTS),
                source      = 'seed',
                condition   = {'threshold': random.randint(50, 99)},
                triggered_at = now - timedelta(minutes=random.randint(0, 1440)),
            ))
        Alert.objects.bulk_create(batch)
        self.stdout.write(f'Created {n} alerts.')

    def _seed_health(self, n):
        from api.telemetry_observability.models.health_status import HealthStatus
        statuses = ['healthy', 'degraded', 'unhealthy', 'unknown']
        batch    = []
        for service in SERVICES[:n]:
            status = random.choices(statuses, weights=[70, 15, 10, 5])[0]
            score  = {'healthy': 100, 'degraded': 60, 'unhealthy': 20, 'unknown': 0}[status]
            batch.append(HealthStatus(
                service_name     = service,
                status           = status,
                health_score     = score + random.randint(-10, 10),
                uptime           = round(random.uniform(95, 100), 3),
                response_time_ms = round(random.uniform(10, 500), 2),
                error_rate       = round(random.uniform(0, 5), 2),
                environment      = 'production',
            ))
        HealthStatus.objects.bulk_create(batch, update_conflicts=True,
            update_fields=['status', 'health_score', 'uptime', 'response_time_ms', 'error_rate'],
            unique_fields=['service_name', 'component_name', 'environment'])
        self.stdout.write(f'Created/updated {len(batch)} health records.')
