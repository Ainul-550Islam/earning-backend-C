from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('admin_panel', '0004_sitecontent_tenant_sitenotification_tenant_and_more'),
    ]
    operations = [
        migrations.AlterField(
            model_name='endpointtoggle',
            name='path',
            field=models.CharField(db_index=True, max_length=500),
        ),
        migrations.AlterUniqueTogether(
            name='endpointtoggle',
            unique_together={('path', 'method')},
        ),
    ]
