from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smartlink', '0007_publisher_domain'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostbackLog',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True)),
                ('click_id',       models.CharField(blank=True, db_index=True, max_length=50)),
                ('offer_id',       models.CharField(blank=True, db_index=True, max_length=20)),
                ('event',          models.CharField(db_index=True, default='lead', max_length=20)),
                ('payout',         models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('currency',       models.CharField(default='USD', max_length=3)),
                ('transaction_id', models.CharField(blank=True, db_index=True, max_length=255)),
                ('sub1',           models.CharField(blank=True, max_length=255)),
                ('adv_sub1',       models.CharField(blank=True, max_length=255)),
                ('ip',             models.GenericIPAddressField(blank=True, null=True)),
                ('is_duplicate',   models.BooleanField(default=False)),
                ('is_attributed',  models.BooleanField(default=False)),
                ('raw_params',     models.JSONField(blank=True, default=dict)),
                ('created_at',     models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'db_table': 'sl_postback_log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='postbacklog',
            index=models.Index(fields=['offer_id', 'created_at'], name='pb_offer_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='postbacklog',
            index=models.Index(fields=['click_id'], name='pb_click_idx'),
        ),
        migrations.AddIndex(
            model_name='postbacklog',
            index=models.Index(fields=['transaction_id'], name='pb_txn_idx'),
        ),
    ]
