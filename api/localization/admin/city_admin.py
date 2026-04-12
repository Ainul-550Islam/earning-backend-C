# admin/city_admin.py
from django.contrib import admin
from ..models.core import City

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'native_name', 'country', 'is_capital', 'is_active', 'population']
    list_filter = ['is_active', 'is_capital', 'country']
    search_fields = ['name', 'native_name']
    raw_id_fields = ['country', 'timezone']
    ordering = ['country__name', 'name']
