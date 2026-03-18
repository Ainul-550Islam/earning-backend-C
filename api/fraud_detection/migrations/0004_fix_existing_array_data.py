from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('fraud_detection', '0003_merge_20260318_1038'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE fraud_detection_userriskprofile
                SET warning_flags = ARRAY[]::varchar[]
                WHERE warning_flags::text = '[]';

                UPDATE fraud_detection_fraudpattern
                SET features = ARRAY[]::varchar[]
                WHERE features::text = '[]';

                UPDATE fraud_detection_ipreputation
                SET threat_types = ARRAY[]::varchar[]
                WHERE threat_types::text = '[]';
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
