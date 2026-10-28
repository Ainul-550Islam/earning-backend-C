"""
tasks/management/commands/seed_task_configs.py
Seed default TaskRetryConfig, TaskQueue, and TaskAlert records.

Usage:
  python manage.py seed_task_configs
  python manage.py seed_task_configs --force   (overwrite existing)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Seed default task system configuration records'

    DEFAULT_QUEUES = [
        {'name': 'default',   'priority_level': 5, 'max_concurrency': 4,  'description': 'Default task queue'},
        {'name': 'high',      'priority_level': 9, 'max_concurrency': 8,  'description': 'High-priority tasks'},
        {'name': 'low',       'priority_level': 2, 'max_concurrency': 2,  'description': 'Low-priority background tasks'},
        {'name': 'reports',   'priority_level': 3, 'max_concurrency': 2,  'description': 'Report generation'},
        {'name': 'payments',  'priority_level': 8, 'max_concurrency': 4,  'description': 'Payment processing'},
        {'name': 'ml',        'priority_level': 4, 'max_concurrency': 2,  'description': 'ML inference and training'},
        {'name': 'exports',   'priority_level': 3, 'max_concurrency': 2,  'description': 'Data exports'},
        {'name': 'emails',    'priority_level': 6, 'max_concurrency': 4,  'description': 'Email/notification dispatch'},
    ]

    DEFAULT_RETRY_CONFIGS = [
        {
            'task_name': 'tasks.payment_tasks.process_withdrawal_requests',
            'max_retries': 5,
            'retry_backoff': 'exponential',
            'retry_delay_seconds': 60,
            'backoff_multiplier': 2.0,
            'send_to_dlq_on_exhaustion': True,
        },
        {
            'task_name': 'tasks.payment_tasks.payment_reconcile',
            'max_retries': 3,
            'retry_backoff': 'exponential',
            'retry_delay_seconds': 120,
            'backoff_multiplier': 2.0,
            'send_to_dlq_on_exhaustion': True,
        },
        {
            'task_name': 'tasks.notification_tasks.send_push_notification',
            'max_retries': 3,
            'retry_backoff': 'linear',
            'retry_delay_seconds': 30,
            'backoff_multiplier': 1.5,
            'send_to_dlq_on_exhaustion': False,
        },
        {
            'task_name': 'tasks.localization_tasks.update_exchange_rates',
            'max_retries': 5,
            'retry_backoff': 'exponential',
            'retry_delay_seconds': 60,
            'backoff_multiplier': 2.0,
            'send_to_dlq_on_exhaustion': False,
        },
        {
            'task_name': 'tasks.referral_tasks.commission_processing',
            'max_retries': 3,
            'retry_backoff': 'exponential',
            'retry_delay_seconds': 60,
            'backoff_multiplier': 2.0,
            'send_to_dlq_on_exhaustion': True,
        },
        {
            'task_name': 'tasks.analytics_tasks.daily_analytics_rollup',
            'max_retries': 2,
            'retry_backoff': 'constant',
            'retry_delay_seconds': 300,
            'backoff_multiplier': 1.0,
            'send_to_dlq_on_exhaustion': False,
        },
    ]

    DEFAULT_ALERTS = [
        {
            'task_name': '*',
            'alert_type': 'failure',
            'severity': 'critical',
            'threshold': 50.0,
            'cooldown_minutes': 30,
            'description': 'Fire when >50% of any task fails in 1 hour',
        },
        {
            'task_name': 'tasks.payment_tasks.process_withdrawal_requests',
            'alert_type': 'failure',
            'severity': 'critical',
            'threshold': 10.0,
            'cooldown_minutes': 15,
            'description': 'Payment task failure rate > 10%',
        },
        {
            'task_name': 'tasks.payment_tasks.payment_reconcile',
            'alert_type': 'missing',
            'severity': 'warning',
            'threshold': 120.0,
            'cooldown_minutes': 60,
            'description': 'Reconcile task not run in 2 hours',
        },
        {
            'task_name': 'default',
            'alert_type': 'depth',
            'severity': 'warning',
            'threshold': 200.0,
            'cooldown_minutes': 30,
            'description': 'Default queue depth > 200',
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Overwrite existing records')

    def handle(self, *args, **options):
        force = options['force']
        self.stdout.write('\nSeeding task configuration...')
        self.stdout.write('-' * 50)

        self._seed_queues(force)
        self._seed_retry_configs(force)
        self._seed_alerts(force)

        self.stdout.write(self.style.SUCCESS('\n[DONE] Task configuration seeded successfully.'))

    def _seed_queues(self, force):
        from api.tasks.models.queue import TaskQueue
        created = updated = 0
        for data in self.DEFAULT_QUEUES:
            if force:
                TaskQueue.objects.update_or_create(name=data['name'], defaults=data)
                updated += 1
            else:
                _, c = TaskQueue.objects.get_or_create(name=data['name'], defaults=data)
                if c:
                    created += 1
        self.stdout.write(f'  TaskQueues: {created} created, {updated} updated')

    def _seed_retry_configs(self, force):
        from api.tasks.models.queue import TaskRetryConfig
        created = updated = 0
        for data in self.DEFAULT_RETRY_CONFIGS:
            task_name = data.pop('task_name') if isinstance(data, dict) else data['task_name']
            data_copy = dict(self.DEFAULT_RETRY_CONFIGS[self.DEFAULT_RETRY_CONFIGS.index(
                next(d for d in self.DEFAULT_RETRY_CONFIGS if d.get('task_name') == task_name)
            )])
            data_copy.pop('task_name', None)
            if force:
                TaskRetryConfig.objects.update_or_create(task_name=task_name, defaults=data_copy)
                updated += 1
            else:
                _, c = TaskRetryConfig.objects.get_or_create(task_name=task_name, defaults=data_copy)
                if c:
                    created += 1
        self.stdout.write(f'  TaskRetryConfigs: {created} created, {updated} updated')

    def _seed_alerts(self, force):
        from api.tasks.models.monitoring import TaskAlert
        created = updated = 0
        for data in self.DEFAULT_ALERTS:
            key  = {'task_name': data['task_name'], 'alert_type': data['alert_type']}
            defs = {k: v for k, v in data.items() if k not in key}
            if force:
                TaskAlert.objects.update_or_create(**key, defaults=defs)
                updated += 1
            else:
                _, c = TaskAlert.objects.get_or_create(**key, defaults=defs)
                if c:
                    created += 1
        self.stdout.write(f'  TaskAlerts: {created} created, {updated} updated')
