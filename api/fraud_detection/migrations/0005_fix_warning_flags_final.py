from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('fraud_detection', '0004_fix_existing_array_data'),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE fraud_detection_userriskprofile 
                SET warning_flags = ARRAY[]::varchar[]
                WHERE warning_flags IS NULL 
                   OR warning_flags::text = '[]'
                   OR warning_flags::text = '{}';
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
