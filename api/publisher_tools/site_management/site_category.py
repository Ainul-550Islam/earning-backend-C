# api/publisher_tools/site_management/site_category.py
"""Site Category — Category management and content classification."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class SiteCategory(TimeStampedModel):
    """Site content categories with IAB taxonomy support。"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitecat_tenant', db_index=True)
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent      = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    iab_code    = models.CharField(max_length=20, blank=True, help_text=_("IAB Content Taxonomy code"))
    is_active   = models.BooleanField(default=True)
    sort_order  = models.IntegerField(default=0)
    icon        = models.CharField(max_length=50, blank=True)
    color_hex   = models.CharField(max_length=10, blank=True)
    # Ad performance hints
    avg_ecpm_tier = models.CharField(max_length=10, choices=[('low','Low'),('medium','Medium'),('high','High'),('premium','Premium')], default='medium')
    advertiser_demand = models.CharField(max_length=10, choices=[('low','Low'),('medium','Medium'),('high','High')], default='medium')
    is_sensitive     = models.BooleanField(default=False, help_text=_("Requires special approval"))
    is_adult_content = models.BooleanField(default=False)

    class Meta:
        db_table = 'publisher_tools_site_categories'
        verbose_name = _('Site Category')
        verbose_name_plural = _('Site Categories')
        ordering = ['sort_order', 'name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name


class SiteCategoryMapping(TimeStampedModel):
    """Site to category mapping (many-to-many with metadata)."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitecatmap_tenant', db_index=True)
    site        = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='category_mappings')
    category    = models.ForeignKey(SiteCategory, on_delete=models.CASCADE, related_name='site_mappings')
    is_primary  = models.BooleanField(default=False)
    confidence  = models.DecimalField(max_digits=5, decimal_places=2, default=100.0, help_text=_("How confident are we (0-100)"))
    source      = models.CharField(max_length=20, choices=[('manual','Manual'),('auto','Automated'),('ml','ML Model')], default='manual')

    class Meta:
        db_table = 'publisher_tools_site_category_mappings'
        verbose_name = _('Site Category Mapping')
        unique_together = [['site', 'category']]

    def __str__(self):
        return f"{self.site.domain} → {self.category.name}"
