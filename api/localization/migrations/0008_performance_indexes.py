# migrations/0008_performance_indexes.py
"""
Performance indexes for World #1 localization system.
PostgreSQL-optimized for high-throughput translation lookups.

Run: python manage.py migrate localization 0008
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('localization', '0007_config_formats')]

    operations = [
        # ── Translation table — most-queried ──────────────────────
        # Composite: language + approved + created (for coverage queries)
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql
        # Key + language lookup (most common pattern)
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql

        # ── Translation Memory — fuzzy search ─────────────────────
        # Hash lookup (exact match — O(1))
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql
        # Fuzzy candidate filtering by word count + language pair
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql
        # Usage-based ordering for TM suggestions
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql

        # ── Missing Translation — alert queries ───────────────────
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql

        # ── TranslationKey — category/namespace filtering ─────────
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql

        # ── Exchange Rate — rate lookup ───────────────────────────
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql

        # ── Localization Insight — analytics queries ──────────────
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql

        # ── GeoIP Mapping — range lookup ─────────────────────────
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql

        # ── LocalizedContent — content type + object lookup ──────
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql

        # ── Full-text search on translation value (PostgreSQL only) ─
        # This enables: Translation.objects.filter(value__search='hello')
        migrations.RunSQL(migrations.RunSQL.noop),  # disabled raw sql
    ]
