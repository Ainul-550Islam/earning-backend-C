import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='SupportTicket', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('ticket_number', models.CharField(max_length=20, unique=True)),
            ('subject', models.CharField(max_length=300)),
            ('category', models.CharField(max_length=20, default='other')),
            ('priority', models.CharField(max_length=10, default='medium')),
            ('status', models.CharField(max_length=15, default='open')),
            ('description', models.TextField()),
            ('related_txn_ref', models.CharField(max_length=100, blank=True)),
            ('resolved_at', models.DateTimeField(null=True, blank=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                     related_name='support_tickets', to=settings.AUTH_USER_MODEL)),
            ('assigned_to', models.ForeignKey(null=True, blank=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='assigned_tickets', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Support Ticket', 'ordering': ['-created_at']}),
        migrations.CreateModel(name='TicketMessage', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('message', models.TextField()),
            ('is_staff', models.BooleanField(default=False)),
            ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                       related_name='messages', to='payment_gateways_support.supportticket')),
            ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                       to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Ticket Message', 'ordering': ['created_at']}),
    ]
