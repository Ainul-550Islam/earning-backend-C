# api/admin_panel/management/commands/enable_maintenance.py
"""
Management command: enable or disable maintenance mode.
Usage:
  python manage.py enable_maintenance
  python manage.py enable_maintenance --duration 60 --message "Upgrading database"
  python manage.py enable_maintenance --disable
  python manage.py enable_maintenance --status
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Enable or disable maintenance mode for the platform.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--disable',
            action='store_true',
            default=False,
            help='Disable maintenance mode (deactivate all active windows).',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            default=False,
            help='Check current maintenance mode status.',
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=60,
            help='Duration in minutes (default: 60).',
        )
        parser.add_argument(
            '--message',
            type=str,
            default="We're currently performing maintenance. Please check back soon.",
            help='Maintenance message shown to users.',
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['scheduled', 'emergency', 'upgrade', 'backup'],
            default='emergency',
            help='Maintenance type (default: emergency).',
        )
        parser.add_argument(
            '--notify',
            action='store_true',
            default=False,
            help='Send notification email to all active users.',
        )
        parser.add_argument(
            '--title',
            type=str,
            default='',
            help='Internal title for the maintenance window.',
        )

    def handle(self, *args, **options):
        from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
        from django.core.cache import cache

        # --- Status check ---
        if options['status']:
            is_active = MaintenanceModeService.is_active()
            message = MaintenanceModeService.get_message()

            if is_active:
                self.stdout.write(self.style.ERROR('🔴 MAINTENANCE MODE: ACTIVE'))
                self.stdout.write(f'   Message: {message}')

                try:
                    from api.admin_panel.models.config import MaintenanceWindow
                    active_windows = MaintenanceWindow.objects.filter(is_active=True)
                    for w in active_windows:
                        self.stdout.write(f'   Window: {w.title}')
                        self.stdout.write(f'   Start:  {w.start_at.strftime("%Y-%m-%d %H:%M UTC")}')
                        self.stdout.write(f'   End:    {w.end_at.strftime("%Y-%m-%d %H:%M UTC")}')
                except Exception:
                    pass
            else:
                self.stdout.write(self.style.SUCCESS('🟢 MAINTENANCE MODE: INACTIVE'))
            return

        # --- Disable ---
        if options['disable']:
            result = MaintenanceModeService.disable()
            if result:
                self.stdout.write(self.style.SUCCESS('✅ Maintenance mode DISABLED.'))
                self.stdout.write('   All active maintenance windows deactivated.')
                self.stdout.write('   Maintenance mode cache cleared.')
            else:
                self.stderr.write(self.style.ERROR('❌ Failed to disable maintenance mode.'))
            return

        # --- Enable ---
        duration = options['duration']
        message = options['message']
        maint_type = options['type']
        notify = options['notify']
        title = options['title'] or f'{maint_type.title()} Maintenance — {timezone.now().strftime("%Y-%m-%d %H:%M")}'

        from datetime import timedelta
        try:
            from api.admin_panel.models.config import MaintenanceWindow
            window = MaintenanceWindow.objects.create(
                title=title,
                message=message,
                maintenance_type=maint_type,
                start_at=timezone.now(),
                end_at=timezone.now() + timedelta(minutes=duration),
                is_active=True,
                notify_users=notify,
                internal_note=f'Created via CLI by management command at {timezone.now().isoformat()}',
            )
            ttl = duration * 60 + 120
            cache.set('admin_panel:maintenance_mode_active', True, ttl)
            cache.set('admin_panel:maintenance_message', message, 86400)

            self.stdout.write(self.style.WARNING(f'🔴 MAINTENANCE MODE: ENABLED'))
            self.stdout.write(f'   Title:    {title}')
            self.stdout.write(f'   Type:     {maint_type}')
            self.stdout.write(f'   Duration: {duration} minutes')
            self.stdout.write(f'   Start:    {window.start_at.strftime("%Y-%m-%d %H:%M UTC")}')
            self.stdout.write(f'   End:      {window.end_at.strftime("%Y-%m-%d %H:%M UTC")}')
            self.stdout.write(f'   Message:  {message}')

            if notify:
                try:
                    from api.admin_panel.services.AdminNotificationService import AdminNotificationService
                    sent = AdminNotificationService.notify_maintenance_upcoming(window)
                    if sent:
                        self.stdout.write('   📧 User notifications sent.')
                    else:
                        self.stdout.write(self.style.WARNING('   📧 Notification send returned False.'))
                except Exception as e:
                    self.stderr.write(f'   📧 Notification error: {e}')

            self.stdout.write('')
            self.stdout.write(
                f'To disable: python manage.py enable_maintenance --disable'
            )

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'❌ Failed to enable maintenance mode: {e}'))
            raise