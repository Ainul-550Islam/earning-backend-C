from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('smartlink', '0001_initial_smartlink'),
    ]

    operations = [
        migrations.CreateModel(
            name='TargetingRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('logic', models.CharField(choices=[('AND', 'All rules must match'), ('OR', 'Any rule must match')], default='AND', max_length=3)),
                ('is_active', models.BooleanField(default=True)),
                ('priority', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('smartlink', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='targeting_rule', to='smartlink.smartlink')),
            ],
            options={'db_table': 'sl_targeting_rule'},
        ),
        migrations.CreateModel(
            name='GeoTargeting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('mode', models.CharField(choices=[('whitelist', 'Whitelist'), ('blacklist', 'Blacklist')], default='whitelist', max_length=10)),
                ('countries', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=2), blank=True, default=list, size=None)),
                ('regions', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=100), blank=True, default=list, size=None)),
                ('cities', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=100), blank=True, default=list, size=None)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='geo_targeting', to='smartlink.targetingrule')),
            ],
            options={'db_table': 'sl_geo_targeting'},
        ),
        migrations.CreateModel(
            name='DeviceTargeting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('mode', models.CharField(default='whitelist', max_length=10)),
                ('device_types', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=10), blank=True, default=list, size=None)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='device_targeting', to='smartlink.targetingrule')),
            ],
            options={'db_table': 'sl_device_targeting'},
        ),
        migrations.CreateModel(
            name='OSTargeting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('mode', models.CharField(default='whitelist', max_length=10)),
                ('os_types', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=10), blank=True, default=list, size=None)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='os_targeting', to='smartlink.targetingrule')),
            ],
            options={'db_table': 'sl_os_targeting'},
        ),
        migrations.CreateModel(
            name='BrowserTargeting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('mode', models.CharField(default='whitelist', max_length=10)),
                ('browsers', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=10), blank=True, default=list, size=None)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='browser_targeting', to='smartlink.targetingrule')),
            ],
            options={'db_table': 'sl_browser_targeting'},
        ),
        migrations.CreateModel(
            name='TimeTargeting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('days_of_week', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), blank=True, default=list, size=None)),
                ('start_hour', models.PositiveSmallIntegerField(default=0)),
                ('end_hour', models.PositiveSmallIntegerField(default=23)),
                ('timezone_name', models.CharField(default='UTC', max_length=50)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='time_targeting', to='smartlink.targetingrule')),
            ],
            options={'db_table': 'sl_time_targeting'},
        ),
        migrations.CreateModel(
            name='ISPTargeting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('mode', models.CharField(default='whitelist', max_length=10)),
                ('isps', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=100), blank=True, default=list, size=None)),
                ('asns', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=20), blank=True, default=list, size=None)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='isp_targeting', to='smartlink.targetingrule')),
            ],
            options={'db_table': 'sl_isp_targeting'},
        ),
        migrations.CreateModel(
            name='LanguageTargeting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('mode', models.CharField(default='whitelist', max_length=10)),
                ('languages', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=10), blank=True, default=list, size=None)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='language_targeting', to='smartlink.targetingrule')),
            ],
            options={'db_table': 'sl_language_targeting'},
        ),
    ]
