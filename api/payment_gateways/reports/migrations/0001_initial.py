# api/payment_gateways/reports/migrations/0001_initial.py
from django.db import migrations, models

class Migration(migrations.Migration):
    initial      = True
    dependencies  = []
    operations   = [
        migrations.CreateModel(name='ReconciliationReport', fields=[
            ('id',          models.BigAutoField(primary_key=True)),
            ('created_at',  models.DateTimeField(auto_now_add=True)),
            ('updated_at',  models.DateTimeField(auto_now=True)),
            ('report_date', models.DateField(unique=True)),
            ('data',        models.JSONField(default=dict)),
        ], options={'verbose_name':'Reconciliation Report','ordering':['-report_date']}),
    ]
