"""CATEGORY_TAXONOMY/category_attributes.py — Which attributes apply per category"""
from django.db import models


class CategoryAttributeSchema(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="category_attr_schemas_tenant")
    category    = models.ForeignKey("marketplace.Category", on_delete=models.CASCADE, related_name="attribute_schema")
    attr_name   = models.CharField(max_length=100)
    attr_type   = models.CharField(max_length=20, choices=[("text","Text"),("number","Number"),("list","List"),("boolean","Boolean")])
    options     = models.TextField(blank=True, help_text="Comma-separated options for 'list' type")
    is_required = models.BooleanField(default=False)
    is_filterable= models.BooleanField(default=True)
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label="marketplace"; db_table="marketplace_category_attr_schema"
        unique_together=[("category","attr_name")]

    def get_options(self): return [o.strip() for o in self.options.split(",") if o.strip()]


def get_required_attributes(category) -> list:
    return list(CategoryAttributeSchema.objects.filter(category=category, is_required=True).values("attr_name","attr_type","options").order_by("sort_order"))


def get_filterable_attributes(category) -> list:
    return list(CategoryAttributeSchema.objects.filter(category=category, is_filterable=True).values("attr_name","attr_type","options").order_by("sort_order"))
