from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SmartLinkGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('color', models.CharField(default='#6366f1', max_length=7)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('publisher', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='smartlink_groups',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'smartlink_group', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='SmartLinkTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50, unique=True)),
                ('color', models.CharField(default='#10b981', max_length=7)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'smartlink_tag', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='SmartLink',
            fields=[
                ('id', models.BigAutoField(primary_key=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('slug', models.CharField(db_index=True, max_length=32, unique=True)),
                ('type', models.CharField(choices=[
                    ('general', 'General'), ('geo_specific', 'Geo Specific'),
                    ('device_specific', 'Device Specific'), ('offer_specific', 'Offer Specific'),
                    ('ab_test', 'A/B Test'), ('campaign', 'Campaign'),
                ], default='general', max_length=20)),
                ('redirect_type', models.CharField(
                    choices=[('302', 'HTTP 302'), ('301', 'HTTP 301'), ('meta', 'Meta Refresh'), ('js', 'JavaScript')],
                    default='302', max_length=5,
                )),
                ('rotation_method', models.CharField(
                    choices=[
                        ('weighted', 'Weighted Random'), ('round_robin', 'Round Robin'),
                        ('epc_optimized', 'EPC Optimized'), ('priority', 'Priority Based'),
                    ],
                    default='weighted', max_length=20,
                )),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('enable_ab_test', models.BooleanField(default=False)),
                ('enable_fraud_filter', models.BooleanField(default=True)),
                ('enable_bot_filter', models.BooleanField(default=True)),
                ('enable_unique_click', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('total_clicks', models.PositiveBigIntegerField(default=0)),
                ('total_unique_clicks', models.PositiveBigIntegerField(default=0)),
                ('total_conversions', models.PositiveBigIntegerField(default=0)),
                ('total_revenue', models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ('last_click_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('publisher', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='smartlinks',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('group', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='smartlinks',
                    to='smartlink.smartlinkgroup',
                )),
            ],
            options={'db_table': 'smartlink', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='SmartLinkTagging',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('smartlink', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smartlink.smartlink')),
                ('tag', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='smartlink.smartlinktag')),
            ],
            options={'db_table': 'smartlink_tagging', 'unique_together': {('smartlink', 'tag')}},
        ),
        migrations.CreateModel(
            name='SmartLinkFallback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('url', models.URLField(max_length=2048)),
                ('reason', models.CharField(blank=True, max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('smartlink', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fallback',
                    to='smartlink.smartlink',
                )),
            ],
            options={'db_table': 'smartlink_fallback'},
        ),
        migrations.CreateModel(
            name='SmartLinkRotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('method', models.CharField(default='weighted', max_length=20)),
                ('auto_optimize_epc', models.BooleanField(default=False)),
                ('optimization_interval_minutes', models.PositiveSmallIntegerField(default=30)),
                ('epc_min_clicks', models.PositiveSmallIntegerField(default=10)),
                ('last_optimized_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('smartlink', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rotation_config',
                    to='smartlink.smartlink',
                )),
            ],
            options={'db_table': 'smartlink_rotation'},
        ),
        migrations.CreateModel(
            name='SmartLinkVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('traffic_split', models.PositiveSmallIntegerField(default=50)),
                ('is_control', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('is_winner', models.BooleanField(default=False)),
                ('clicks', models.PositiveBigIntegerField(default=0)),
                ('conversions', models.PositiveBigIntegerField(default=0)),
                ('revenue', models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('smartlink', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versions',
                    to='smartlink.smartlink',
                )),
            ],
            options={'db_table': 'smartlink_version'},
        ),
        migrations.AddIndex(
            model_name='smartlink',
            index=models.Index(fields=['slug'], name='sl_slug_idx'),
        ),
        migrations.AddIndex(
            model_name='smartlink',
            index=models.Index(fields=['publisher', 'is_active'], name='sl_pub_active_idx'),
        ),
    ]
