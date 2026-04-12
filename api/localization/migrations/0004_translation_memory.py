# migrations/0004_translation_memory.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('localization', '0003_exchange_rates')]
    operations = [
        migrations.CreateModel(
            name='TranslationMemory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_text', models.TextField()),
                ('target_text', models.TextField()),
                ('source_hash', models.CharField(max_length=64, db_index=True)),
                ('domain', models.CharField(max_length=100, blank=True, db_index=True)),
                ('usage_count', models.PositiveIntegerField(default=0)),
                ('is_approved', models.BooleanField(default=False)),
                ('quality_rating', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('tags', models.JSONField(default=list, blank=True)),
                ('metadata', models.JSONField(default=dict, blank=True)),
                ('last_used_at', models.DateTimeField(null=True, blank=True)),
                ('source_language', models.ForeignKey('localization.language', on_delete=django.db.models.deletion.CASCADE, related_name='tm_source')),
                ('target_language', models.ForeignKey('localization.language', on_delete=django.db.models.deletion.CASCADE, related_name='tm_target')),
            ],
            options={'verbose_name': 'Translation Memory', 'ordering': ['-usage_count']},
        ),
        migrations.CreateModel(
            name='TranslationGlossary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_term', models.CharField(max_length=500)),
                ('definition', models.TextField(blank=True)),
                ('domain', models.CharField(max_length=100, blank=True, db_index=True)),
                ('is_do_not_translate', models.BooleanField(default=False)),
                ('is_brand_term', models.BooleanField(default=False)),
                ('is_forbidden', models.BooleanField(default=False)),
                ('notes', models.TextField(blank=True)),
                ('tags', models.JSONField(default=list, blank=True)),
                ('usage_count', models.PositiveIntegerField(default=0)),
                ('source_language', models.ForeignKey('localization.language', on_delete=django.db.models.deletion.CASCADE, related_name='glossary_source')),
            ],
            options={'verbose_name': 'Translation Glossary', 'ordering': ['source_term']},
        ),
        migrations.CreateModel(
            name='TranslationVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('version_number', models.PositiveIntegerField(default=1)),
                ('value', models.TextField()),
                ('value_plural', models.TextField(blank=True, default='')),
                ('source', models.CharField(max_length=20, default='manual')),
                ('is_approved', models.BooleanField(default=False)),
                ('word_count', models.PositiveIntegerField(null=True, blank=True)),
                ('char_count', models.PositiveIntegerField(null=True, blank=True)),
                ('translation', models.ForeignKey('localization.translation', on_delete=django.db.models.deletion.CASCADE, related_name='versions')),
            ],
            options={'verbose_name': 'Translation Version', 'ordering': ['-version_number']},
        ),
    ]
