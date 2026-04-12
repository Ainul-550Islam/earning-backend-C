from django.core.management.base import BaseCommand
from dr_integration.services import DRBackupBridge

class Command(BaseCommand):
    help = 'Trigger a DR-managed backup'
    def add_arguments(self, parser):
        parser.add_argument('--type', choices=['full','incremental','differential'],
                             default='incremental', dest='backup_type')
        parser.add_argument('--dry-run', action='store_true')
    def handle(self, *args, **options):
        if options['dry_run']:
            self.stdout.write(f"[DRY RUN] Would trigger {options['backup_type']} backup"); return
        bridge = DRBackupBridge()
        result = bridge.trigger_backup(backup_type=options['backup_type'], actor_id='manage_py')
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f"✅ Backup triggered: {result.get('job_id')} [{result.get('backup_type')}]"))
        else:
            self.stderr.write(f"❌ Backup failed: {result.get('error')}")
