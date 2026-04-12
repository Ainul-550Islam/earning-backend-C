from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    """
    Migration 0007: PublisherSubID, PublisherAllowList, PublisherBlockList models
    """
    dependencies = [
        ('smartlink', '0006_ab_test'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PublisherSubID',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('sub1_label', models.CharField(blank=True, default='sub1', max_length=50)),
                ('sub2_label', models.CharField(blank=True, default='sub2', max_length=50)),
                ('sub3_label', models.CharField(blank=True, default='sub3', max_length=50)),
                ('sub4_label', models.CharField(blank=True, default='sub4', max_length=50)),
                ('sub5_label', models.CharField(blank=True, default='sub5', max_length=50)),
                ('sub1_required', models.BooleanField(default=False)),
                ('sub2_required', models.BooleanField(default=False)),
                ('sub3_required', models.BooleanField(default=False)),
                ('sub4_required', models.BooleanField(default=False)),
                ('sub5_required', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('publisher', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sub_id_definitions',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('smartlink', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sub_id_definitions',
                    to='smartlink.smartlink',
                )),
            ],
            options={'db_table': 'sl_publisher_sub_id'},
        ),
        migrations.CreateModel(
            name='PublisherAllowList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('category', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('publisher', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='allowed_categories',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('granted_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='granted_allowlists',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sl_publisher_allowlist'},
        ),
        migrations.CreateModel(
            name='PublisherBlockList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('category', models.CharField(blank=True, max_length=100)),
                ('reason', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('publisher', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blocked_advertisers',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('blocked_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_blocklists',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'sl_publisher_blocklist'},
        ),
    ]
