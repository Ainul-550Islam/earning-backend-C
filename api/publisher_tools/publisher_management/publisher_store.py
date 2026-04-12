# api/publisher_tools/publisher_management/publisher_store.py
"""Publisher Store — Public profile page, portfolio, ad inventory showcase।"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PublisherStore(TimeStampedModel):
    """Publisher-এর public store/portfolio page।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_pubstore_tenant', db_index=True)

    publisher        = models.OneToOneField('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='store')
    slug             = models.SlugField(max_length=100, unique=True, db_index=True)
    is_public        = models.BooleanField(default=False)
    headline         = models.CharField(max_length=300, blank=True)
    sub_headline     = models.CharField(max_length=500, blank=True)
    about_text       = models.TextField(blank=True)
    cta_text         = models.CharField(max_length=100, default='Contact Us')
    cta_url          = models.URLField(blank=True)
    featured_sites   = models.ManyToManyField('publisher_tools.Site', blank=True, related_name='featured_in_stores')
    featured_apps    = models.ManyToManyField('publisher_tools.App', blank=True, related_name='featured_in_stores')
    show_revenue_stats  = models.BooleanField(default=False, help_text=_("Show aggregate revenue stats publicly"))
    show_audience_stats = models.BooleanField(default=True)
    show_ad_formats     = models.BooleanField(default=True)
    show_contact_form   = models.BooleanField(default=True)
    show_social_links   = models.BooleanField(default=True)
    # SEO
    meta_title          = models.CharField(max_length=200, blank=True)
    meta_description    = models.CharField(max_length=400, blank=True)
    # Stats (cached)
    total_pageviews     = models.BigIntegerField(default=0)
    unique_visitors     = models.BigIntegerField(default=0)
    contact_form_submissions = models.IntegerField(default=0)
    last_updated_at     = models.DateTimeField(auto_now=True)
    metadata            = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_stores'
        verbose_name = _('Publisher Store')
        verbose_name_plural = _('Publisher Stores')

    def __str__(self):
        return f"Store: {self.slug} ({'public' if self.is_public else 'private'})"

    @property
    def store_url(self):
        return f"https://publishertools.io/publisher/{self.slug}"

    def increment_view(self):
        self.total_pageviews += 1
        self.unique_visitors += 1
        self.save(update_fields=['total_pageviews', 'unique_visitors'])


class StoreContactMessage(TimeStampedModel):
    """Store page-এ contact form submissions।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_storecontact_tenant', db_index=True)
    store            = models.ForeignKey(PublisherStore, on_delete=models.CASCADE, related_name='contact_messages')
    sender_name      = models.CharField(max_length=200)
    sender_email     = models.EmailField()
    sender_company   = models.CharField(max_length=200, blank=True)
    subject          = models.CharField(max_length=300)
    message          = models.TextField()
    advertiser_budget= models.CharField(max_length=50, blank=True)
    preferred_formats= models.JSONField(default=list, blank=True)
    is_read          = models.BooleanField(default=False)
    is_replied       = models.BooleanField(default=False)
    replied_at       = models.DateTimeField(null=True, blank=True)
    ip_address       = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'publisher_tools_store_contact_messages'
        verbose_name = _('Store Contact Message')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.store.slug} — {self.sender_name}: {self.subject[:50]}"
