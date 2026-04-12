# migrations/0005_localized_content.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('localization', '0004_translation_memory')]
    operations = [
        migrations.CreateModel(
            name='LocalizedContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('content_type', models.CharField(max_length=100, db_index=True)),
                ('object_id', models.CharField(max_length=255, db_index=True)),
                ('field_name', models.CharField(max_length=100)),
                ('value', models.TextField()),
                ('is_approved', models.BooleanField(default=False)),
                ('is_machine_translated', models.BooleanField(default=False)),
                ('review_status', models.CharField(max_length=20, default='pending')),
                ('word_count', models.PositiveIntegerField(null=True, blank=True)),
                ('character_count', models.PositiveIntegerField(null=True, blank=True)),
                ('metadata', models.JSONField(default=dict, blank=True)),
                ('language', models.ForeignKey('localization.language', on_delete=django.db.models.deletion.CASCADE, related_name='localized_content')),
            ],
            options={'verbose_name': 'Localized Content', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='LocalizedSEO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('content_type', models.CharField(max_length=100, db_index=True)),
                ('object_id', models.CharField(max_length=255, db_index=True)),
                ('meta_title', models.CharField(max_length=200, blank=True)),
                ('meta_description', models.TextField(blank=True)),
                ('og_title', models.CharField(max_length=200, blank=True)),
                ('og_description', models.TextField(blank=True)),
                ('og_image_url', models.URLField(blank=True)),
                ('hreflang_tags', models.JSONField(default=dict, blank=True)),
                ('canonical_url', models.URLField(blank=True)),
                ('is_indexable', models.BooleanField(default=True)),
                ('language', models.ForeignKey('localization.language', on_delete=django.db.models.deletion.CASCADE, related_name='localized_seo')),
            ],
            options={'verbose_name': 'Localized SEO'},
        ),
        migrations.AlterUniqueTogether(
            name='localizedcontent',
            unique_together={('content_type', 'object_id', 'language', 'field_name')},
        ),
        migrations.AlterUniqueTogether(
            name='localizedseo',
            unique_together={('content_type', 'object_id', 'language')},
        ),
    ]
