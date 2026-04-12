from django.db import migrations


class Migration(migrations.Migration):
    """
    Migration 0006: A/B test result and publisher domain tables
    are included in migration 0005_analytics.py already.
    This is a no-op placeholder for correct dependency chain.
    """
    dependencies = [
        ('smartlink', '0005_analytics'),
    ]

    operations = []
