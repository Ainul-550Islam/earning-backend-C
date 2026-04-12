# migrations/0007_config_formats.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('localization', '0006_analytics')]
    operations = [
        migrations.CreateModel(
            name='LocalizationConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant_id', models.CharField(max_length=100, unique=True, db_index=True)),
                ('detect_language_from_browser', models.BooleanField(default=True)),
                ('detect_language_from_ip', models.BooleanField(default=True)),
                ('auto_translate_missing', models.BooleanField(default=False)),
                ('require_translation_approval', models.BooleanField(default=True)),
                ('show_untranslated_keys', models.BooleanField(default=True)),
                ('translation_cache_ttl', models.PositiveIntegerField(default=3600)),
                ('enable_rtl_support', models.BooleanField(default=True)),
                ('enable_translation_memory', models.BooleanField(default=True)),
                ('enable_glossary', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('custom_settings', models.JSONField(default=dict, blank=True)),
                ('default_language', models.ForeignKey('localization.language', null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='config_default')),
                ('default_currency', models.ForeignKey('localization.currency', null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='config_default')),
            ],
            options={'verbose_name': 'Localization Config'},
        ),
        migrations.CreateModel(
            name='DateTimeFormat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('calendar_system', models.CharField(max_length=30, default='gregorian')),
                ('date_short', models.CharField(max_length=30, default='MM/dd/yyyy')),
                ('date_medium', models.CharField(max_length=40, default='MMM d, yyyy')),
                ('date_long', models.CharField(max_length=50, default='MMMM d, yyyy')),
                ('time_short', models.CharField(max_length=20, default='h:mm a')),
                ('time_medium', models.CharField(max_length=30, default='h:mm:ss a')),
                ('first_day_of_week', models.PositiveSmallIntegerField(default=1)),
                ('am_symbol', models.CharField(max_length=10, default='AM')),
                ('pm_symbol', models.CharField(max_length=10, default='PM')),
                ('month_names', models.JSONField(default=list, blank=True)),
                ('day_names', models.JSONField(default=list, blank=True)),
                ('use_native_numerals', models.BooleanField(default=False)),
                ('language', models.ForeignKey('localization.language', on_delete=django.db.models.deletion.CASCADE, related_name='datetime_formats')),
                ('country', models.ForeignKey('localization.country', null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='datetime_formats')),
            ],
            options={'verbose_name': 'DateTime Format'},
        ),
        migrations.CreateModel(
            name='NumberFormat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('decimal_symbol', models.CharField(max_length=3, default='.')),
                ('grouping_symbol', models.CharField(max_length=3, default=',')),
                ('grouping_size', models.PositiveSmallIntegerField(default=3)),
                ('secondary_grouping', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('native_digits', models.CharField(max_length=20, blank=True)),
                ('percent_symbol', models.CharField(max_length=5, default='%')),
                ('number_system', models.CharField(max_length=20, default='latn')),
                ('language', models.ForeignKey('localization.language', on_delete=django.db.models.deletion.CASCADE, related_name='number_formats')),
            ],
            options={'verbose_name': 'Number Format'},
        ),
    ]
