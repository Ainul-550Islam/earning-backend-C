from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('fraud_detection', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE fraud_detection_userriskprofile
                SET warning_flags = '{}'
                WHERE warning_flags::text = '[]' OR warning_flags IS NULL;

                UPDATE fraud_detection_fraudpattern
                SET features = '{}'
                WHERE features::text = '[]' OR features IS NULL;

                UPDATE fraud_detection_ipreputation
                SET threat_types = '{}'
                WHERE threat_types::text = '[]' OR threat_types IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
