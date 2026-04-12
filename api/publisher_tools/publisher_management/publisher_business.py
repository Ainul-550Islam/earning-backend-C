# api/publisher_tools/publisher_management/publisher_business.py
"""Publisher Business Information — Company details, Tax info, Legal docs।"""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from core.models import TimeStampedModel


class PublisherBusiness(TimeStampedModel):
    """Publisher-এর business/company details।"""

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_pubbusiness_tenant', db_index=True)

    COMPANY_TYPE_CHOICES = [
        ('sole_proprietorship', _('Sole Proprietorship')),
        ('partnership',         _('Partnership')),
        ('llc',                 _('LLC / Limited Liability Company')),
        ('corporation',         _('Corporation / Limited Company')),
        ('ngo',                 _('NGO / Non-profit')),
        ('government',          _('Government Entity')),
        ('freelancer',          _('Individual Freelancer')),
    ]

    BUSINESS_SIZE_CHOICES = [
        ('micro',   _('Micro (1-10 employees)')),
        ('small',   _('Small (11-50 employees)')),
        ('medium',  _('Medium (51-250 employees)')),
        ('large',   _('Large (250+ employees)')),
    ]

    publisher            = models.OneToOneField('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='business_info')
    company_legal_name   = models.CharField(max_length=300, verbose_name=_("Company Legal Name"))
    company_type         = models.CharField(max_length=30, choices=COMPANY_TYPE_CHOICES, default='llc')
    business_size        = models.CharField(max_length=10, choices=BUSINESS_SIZE_CHOICES, default='small')
    registration_number  = models.CharField(max_length=100, blank=True, verbose_name=_("Company Registration Number"))
    registration_country = models.CharField(max_length=100, default='Bangladesh', verbose_name=_("Country of Incorporation"))
    registration_date    = models.DateField(null=True, blank=True, verbose_name=_("Registration Date"))
    tax_id               = models.CharField(max_length=50, blank=True, verbose_name=_("Tax ID / EIN / TIN"))
    vat_number           = models.CharField(max_length=50, blank=True, verbose_name=_("VAT Number"))
    annual_revenue_usd   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, verbose_name=_("Annual Revenue (USD)"))
    employee_count       = models.IntegerField(default=1)
    primary_industry     = models.CharField(max_length=100, blank=True, verbose_name=_("Primary Industry"))
    business_description = models.TextField(blank=True, verbose_name=_("Business Description"))
    registered_address   = models.TextField(verbose_name=_("Registered Address"))
    billing_address      = models.TextField(blank=True, verbose_name=_("Billing Address"))
    billing_email        = models.EmailField(blank=True, verbose_name=_("Billing Email"))
    accounts_payable_contact = models.EmailField(blank=True, verbose_name=_("Accounts Payable Contact"))
    legal_contact_name   = models.CharField(max_length=200, blank=True, verbose_name=_("Legal Contact Name"))
    legal_contact_email  = models.EmailField(blank=True, verbose_name=_("Legal Contact Email"))
    certifications       = models.JSONField(default=list, blank=True, verbose_name=_("Industry Certifications"))
    is_publicly_traded   = models.BooleanField(default=False, verbose_name=_("Publicly Traded Company"))
    stock_ticker         = models.CharField(max_length=10, blank=True, verbose_name=_("Stock Ticker Symbol"))
    # Documents
    certificate_of_incorporation = models.FileField(upload_to='publisher_business/docs/', null=True, blank=True)
    memorandum_of_association    = models.FileField(upload_to='publisher_business/docs/', null=True, blank=True)
    tax_clearance_certificate    = models.FileField(upload_to='publisher_business/docs/', null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_business'
        verbose_name = _('Publisher Business Info')
        verbose_name_plural = _('Publisher Business Info')

    def __str__(self):
        return f"{self.company_legal_name} ({self.publisher.publisher_id})"

    @property
    def is_enterprise_eligible(self):
        return (
            self.company_type in ('llc', 'corporation') and
            (self.annual_revenue_usd or 0) >= Decimal('50000') and
            self.registration_number != ''
        )
