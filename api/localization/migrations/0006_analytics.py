# migrations/0006_analytics.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('localization', '0005_localized_content')]
    operations = [
        migrations.CreateModel(
            name='LocalizationInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField(db_index=True)),
                ('total_requests', models.PositiveIntegerField(default=0)),
                ('unique_users', models.PositiveIntegerField(default=0)),
                ('translation_hits', models.PositiveIntegerField(default=0)),
                ('translation_misses', models.PositiveIntegerField(default=0)),
                ('cache_hits', models.PositiveIntegerField(default=0)),
                ('cache_misses', models.PositiveIntegerField(default=0)),
                ('currency_conversions', models.PositiveIntegerField(default=0)),
                ('language_switches', models.PositiveIntegerField(default=0)),
                ('top_missing_keys', models.JSONField(default=list, blank=True)),
                ('metadata', models.JSONField(default=dict, blank=True)),
                ('language', models.ForeignKey('localization.language', null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='insights')),
                ('country', models.ForeignKey('localization.country', null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='insights')),
            ],
            options={'verbose_name': 'Localization Insight', 'ordering': ['-date']},
        ),
        migrations.CreateModel(
            name='TranslationCoverage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('total_keys', models.PositiveIntegerField(default=0)),
                ('translated_keys', models.PositiveIntegerField(default=0)),
                ('approved_keys', models.PositiveIntegerField(default=0)),
                ('coverage_percent', models.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ('approved_percent', models.DecimalField(max_digits=5, decimal_places=2, default=0)),
                ('missing_keys', models.PositiveIntegerField(default=0)),
                ('last_calculated_at', models.DateTimeField(null=True, blank=True)),
                ('top_missing', models.JSONField(default=list, blank=True)),
                ('language', models.OneToOneField('localization.language', on_delete=django.db.models.deletion.CASCADE, related_name='coverage_stat')),
            ],
            options={'verbose_name': 'Translation Coverage'},
        ),
    ]
