from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.key_rotation')

class Command(BaseCommand):
    help = 'Rotate encryption keys — re-encrypt all sensitive data'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without applying')

    def handle(self, *args, **options):
        from api.promotions.security_vault.secure_storage import SecureStorage
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes applied'))
            return

        # Generate new key
        storage  = SecureStorage()
        old_key  = storage._get_current_key()
        new_key  = storage._generate_new_key()

        # Re-encrypt sensitive fields
        re_encrypted = storage.rotate_keys(old_key, new_key)
        self.stdout.write(self.style.SUCCESS(f'Keys rotated: {re_encrypted} records re-encrypted'))
        logger.critical(f'Encryption key rotation completed: {re_encrypted} records')
