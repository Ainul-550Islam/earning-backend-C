from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("""
                ALTER TABLE fraud_detection_userriskprofile 
                ALTER COLUMN warning_flags SET DEFAULT '{}';
                ALTER TABLE fraud_detection_fraudpattern 
                ALTER COLUMN features SET DEFAULT '{}';
                ALTER TABLE fraud_detection_ipreputation 
                ALTER COLUMN threat_types SET DEFAULT '{}';
                UPDATE fraud_detection_userriskprofile
                SET warning_flags = ARRAY[]::varchar[]
                WHERE warning_flags::text = '[]';
                UPDATE fraud_detection_fraudpattern
                SET features = ARRAY[]::varchar[]
                WHERE features::text = '[]';
                UPDATE fraud_detection_ipreputation
                SET threat_types = ARRAY[]::varchar[]
                WHERE threat_types::text = '[]';
            """)
        self.stdout.write('Array fields fixed!')
