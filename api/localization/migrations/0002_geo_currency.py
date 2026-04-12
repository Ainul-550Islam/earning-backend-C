# migrations/0002_geo_currency.py
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [('localization', '0001_initial')]
    operations = [
        migrations.CreateModel(name='Region', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('name', models.CharField(max_length=200)),
            ('name_native', models.CharField(blank=True, max_length=200)),
            ('code', models.CharField(blank=True, db_index=True, max_length=20)),
            ('region_type', models.CharField(choices=[('continent','Continent'),('subregion','Subregion'),('country','Country'),('state','State/Province'),('district','District'),('city','City/Municipality'),('neighborhood','Neighborhood')], db_index=True, max_length=20)),
            ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
            ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
            ('population', models.BigIntegerField(blank=True, null=True)),
            ('area_km2', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
            ('is_active', models.BooleanField(db_index=True, default=True)),
            ('geoname_id', models.IntegerField(blank=True, null=True, unique=True)),
            ('wikidata_id', models.CharField(blank=True, max_length=20)),
            ('metadata', models.JSONField(blank=True, default=dict)),
            ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='localization.region')),
            ('country', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='regions', to='localization.country')),
            ('timezone', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='regions', to='localization.timezone')),
        ], options={'verbose_name': 'Region', 'ordering': ['region_type', 'name']}),
    ]
