from django.conf import settings; from django.db import migrations, models; import django.db.models.deletion
from decimal import Decimal
class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='PerformanceTier', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('name', models.CharField(max_length=50)),
            ('min_monthly_earnings', models.DecimalField(max_digits=12, decimal_places=2)),
            ('bonus_percent', models.DecimalField(max_digits=5, decimal_places=2)),
            ('min_payout_threshold', models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1'))),
            ('priority_support', models.BooleanField(default=False)),
            ('badge_color', models.CharField(max_length=7, default='#C0C0C0')),
            ('sort_order', models.IntegerField(default=0)),
        ], options={'verbose_name': 'Performance Tier'}),
        migrations.CreateModel(name='PublisherBonus', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('bonus_type', models.CharField(max_length=25)),
            ('amount', models.DecimalField(max_digits=10, decimal_places=2)),
            ('currency', models.CharField(max_length=5, default='USD')),
            ('status', models.CharField(max_length=10, default='pending')),
            ('description', models.TextField(blank=True)),
            ('paid_at', models.DateTimeField(null=True, blank=True)),
            ('period', models.CharField(max_length=20, blank=True)),
            ('publisher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                          related_name='bonuses', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Publisher Bonus'}),
    ]
