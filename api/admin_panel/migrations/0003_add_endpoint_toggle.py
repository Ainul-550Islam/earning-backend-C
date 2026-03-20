from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EndpointToggle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(db_index=True, max_length=500, unique=True)),
                ('method', models.CharField(default='ALL', max_length=10)),
                ('group', models.CharField(default='other', max_length=100)),
                ('label', models.CharField(blank=True, max_length=200)),
                ('is_enabled', models.BooleanField(default=True)),
                ('disabled_message', models.CharField(default='This feature is temporarily disabled.', max_length=500)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['group', 'path'],
                'app_label': 'admin_panel',
            },
        ),
    ]
