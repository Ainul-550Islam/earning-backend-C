"""CATEGORY_TAXONOMY/category_mapper.py — Map external category names to internal"""
from django.db import models
from api.marketplace.models import Category


class CategoryMapping(models.Model):
    tenant       = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                      related_name="category_mappings_tenant")
    external_name= models.CharField(max_length=200, help_text="External source category name")
    internal_cat = models.ForeignKey(Category, on_delete=models.CASCADE)
    source       = models.CharField(max_length=50, blank=True, help_text="e.g. shopify, amazon, csv")

    class Meta:
        app_label="marketplace"; db_table="marketplace_category_mapping"
        unique_together=[("tenant","external_name","source")]


def map_external_category(tenant, external_name: str, source: str = "") -> Category:
    mapping = CategoryMapping.objects.filter(tenant=tenant, external_name__iexact=external_name, source=source).first()
    if mapping:
        return mapping.internal_cat
    # Fuzzy match
    cat = Category.objects.filter(tenant=tenant, name__icontains=external_name.split("/")[-1]).first()
    return cat
