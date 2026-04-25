# models/geo.py
# Region, CountryLanguage, CountryCurrency, GeoIPMapping, PhoneFormat — 5 new models
from django.db import models
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)


class Region(models.Model):
    """Continent / State / District hierarchy — geographic subdivision"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class RegionType(models.TextChoices):
        CONTINENT = 'continent', _('Continent')
        SUBREGION = 'subregion', _('Subregion')
        COUNTRY = 'country', _('Country')
        STATE = 'state', _('State/Province')
        DISTRICT = 'district', _('District')
        CITY = 'city', _('City/Municipality')
        NEIGHBORHOOD = 'neighborhood', _('Neighborhood')

    name = models.CharField(max_length=200)
    name_native = models.CharField(max_length=200, blank=True)
    code = models.CharField(max_length=20, blank=True, db_index=True)
    region_type = models.CharField(max_length=20, choices=RegionType.choices, db_index=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    country = models.ForeignKey('localization.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='regions')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    population = models.BigIntegerField(null=True, blank=True)
    area_km2 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    timezone = models.ForeignKey('localization.Timezone', on_delete=models.SET_NULL, null=True, blank=True, related_name='regions')
    is_active = models.BooleanField(default=True, db_index=True)
    geoname_id = models.IntegerField(null=True, blank=True, unique=True)
    wikidata_id = models.CharField(max_length=20, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['region_type', 'name']
        verbose_name = _("Region")
        verbose_name_plural = _("Regions")
        indexes = [
            models.Index(fields=['region_type', 'is_active'], name='idx_region_type_is_active_1089'),
            models.Index(fields=['country', 'region_type'], name='idx_country_region_type_1090'),
            models.Index(fields=['code'], name='idx_code_1091'),
        ]

    def __str__(self):
        parent_name = f", {self.parent.name}" if self.parent else ""
        return f"{self.name}{parent_name} [{self.region_type}]"

    def get_ancestors(self):
        """Return list of ancestors from root to parent"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def get_full_path(self):
        """e.g. Asia > South Asia > Bangladesh > Dhaka Division"""
        parts = [a.name for a in self.get_ancestors()] + [self.name]
        return " > ".join(parts)


class CountryLanguage(models.Model):
    """Official/national/regional languages per country — extended M2M"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    country = models.ForeignKey('localization.Country', on_delete=models.CASCADE, related_name='country_languages')
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='country_languages')
    is_official = models.BooleanField(default=False)
    is_national = models.BooleanField(default=False)
    is_regional = models.BooleanField(default=False)
    is_minority = models.BooleanField(default=False)
    speaker_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    speaker_count = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default='recognized', choices=[
        ('official','Official'), ('co_official','Co-official'), ('national','National'),
        ('regional','Regional'), ('recognized','Recognized'), ('minority','Minority'),
        ('immigrant','Immigrant'), ('indigenous','Indigenous'),
    ])
    regions_spoken = models.JSONField(default=list, blank=True)
    script_used = models.CharField(max_length=50, blank=True)
    is_taught_in_schools = models.BooleanField(default=False)
    is_used_in_government = models.BooleanField(default=False)
    is_used_in_media = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=999)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['country', 'language']
        ordering = ['country__name', '-speaker_percentage', 'language__name']
        verbose_name = _("Country Language")
        verbose_name_plural = _("Country Languages")
        indexes = [
            models.Index(fields=['country', 'is_official'], name='idx_country_is_official_1092'),
            models.Index(fields=['language'], name='idx_language_1093'),
        ]

    def __str__(self):
        country_code = getattr(self.country, 'code', '?')
        lang_code = getattr(self.language, 'code', '?')
        official = " (Official)" if self.is_official else ""
        return f"{country_code} ↔ {lang_code}{official}"


class CountryCurrency(models.Model):
    """Currencies per country — a country can have multiple currencies"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    country = models.ForeignKey('localization.Country', on_delete=models.CASCADE, related_name='country_currencies')
    currency = models.ForeignKey('localization.Currency', on_delete=models.CASCADE, related_name='country_currencies')
    is_primary = models.BooleanField(default=True, help_text=_("Primary official currency"))
    is_legal_tender = models.BooleanField(default=True)
    is_accepted = models.BooleanField(default=True, help_text=_("Widely accepted (e.g. USD in Ecuador)"))
    introduced_date = models.DateField(null=True, blank=True)
    withdrawn_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['country', 'currency']
        verbose_name = _("Country Currency")
        verbose_name_plural = _("Country Currencies")
        indexes = [models.Index(fields=['country', 'is_primary'], name='idx_country_is_primary_1094')]

    def __str__(self):
        country_code = getattr(self.country, 'code', '?')
        currency_code = getattr(self.currency, 'code', '?')
        primary = " (Primary)" if self.is_primary else ""
        return f"{country_code} → {currency_code}{primary}"


class GeoIPMapping(models.Model):
    """IP address range → country/city/timezone mapping (MaxMind-style)"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ip_start = models.GenericIPAddressField(db_index=True, help_text=_("Start of IP range"))
    ip_end = models.GenericIPAddressField(db_index=True, help_text=_("End of IP range"))
    ip_start_int = models.BigIntegerField(db_index=True, help_text=_("Integer representation of ip_start for range queries"))
    ip_end_int = models.BigIntegerField(db_index=True)
    country = models.ForeignKey('localization.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='geo_ip_mappings')
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    region_name = models.CharField(max_length=100, blank=True)
    city_name = models.CharField(max_length=100, blank=True)
    timezone = models.ForeignKey('localization.Timezone', on_delete=models.SET_NULL, null=True, blank=True, related_name='geo_ip_mappings')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    isp = models.CharField(max_length=200, blank=True)
    org = models.CharField(max_length=200, blank=True)
    asn = models.CharField(max_length=20, blank=True)
    is_vpn = models.BooleanField(default=False)
    is_proxy = models.BooleanField(default=False)
    is_datacenter = models.BooleanField(default=False)
    is_tor = models.BooleanField(default=False)
    threat_score = models.PositiveSmallIntegerField(null=True, blank=True)
    source = models.CharField(max_length=50, default='maxmind', choices=[
        ('maxmind','MaxMind GeoIP2'),('ipinfo','IPinfo'),('ip2location','IP2Location'),
        ('manual','Manual'),('ipapi','ip-api.com'),
    ])
    database_version = models.CharField(max_length=30, blank=True)
    data_date = models.DateField(null=True, blank=True, help_text=_("Date of the GeoIP database snapshot"))

    class Meta:
        ordering = ['ip_start_int']
        verbose_name = _("GeoIP Mapping")
        verbose_name_plural = _("GeoIP Mappings")
        indexes = [
            models.Index(fields=['ip_start_int', 'ip_end_int'], name='idx_ip_start_int_ip_end_in_bec'),
            models.Index(fields=['country_code'], name='idx_country_code_1096'),
        ]

    def __str__(self):
        return f"{self.ip_start} - {self.ip_end} → {self.country_code or 'Unknown'}"

    @classmethod
    def lookup(cls, ip_address):
        """IP address থেকে country/city/timezone খুঁজে বের করে"""
        try:
            import socket, struct
            packed = socket.inet_aton(ip_address)
            ip_int = struct.unpack("!L", packed)[0]
            return cls.objects.filter(
                ip_start_int__lte=ip_int,
                ip_end_int__gte=ip_int
            ).select_related('country', 'timezone').first()
        except Exception as e:
            logger.error(f"GeoIP lookup failed for {ip_address}: {e}")
            return None


class PhoneFormat(models.Model):
    """Phone number format regex per country"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    country = models.OneToOneField('localization.Country', on_delete=models.CASCADE, related_name='phone_format')
    country_dial_code = models.CharField(max_length=5, help_text=_("International dial code e.g. +880"))
    national_prefix = models.CharField(max_length=5, blank=True, help_text=_("National trunk prefix e.g. 0"))
    mobile_pattern = models.CharField(max_length=100, blank=True, help_text=_("Regex for mobile numbers"))
    landline_pattern = models.CharField(max_length=100, blank=True)
    mobile_length = models.PositiveSmallIntegerField(null=True, blank=True)
    landline_length = models.PositiveSmallIntegerField(null=True, blank=True)
    display_format = models.CharField(max_length=50, blank=True, help_text=_("e.g. +880 1X-XXXX-XXXX"))
    input_mask = models.CharField(max_length=50, blank=True)
    example_mobile = models.CharField(max_length=20, blank=True)
    example_landline = models.CharField(max_length=20, blank=True)
    emergency_numbers = models.JSONField(default=dict, blank=True, help_text=_("e.g. {police: 999, fire: 199}"))
    operators = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Phone Format")
        verbose_name_plural = _("Phone Formats")

    def __str__(self):
        country_code = getattr(self.country, 'code', '?')
        return f"Phone format for {country_code} ({self.country_dial_code})"

    def validate_number(self, number):
        """Phone number validate করে"""
        import re
        try:
            digits = re.sub(r'\D', '', number)
            if self.mobile_pattern:
                if re.match(self.mobile_pattern, digits):
                    return {'valid': True, 'type': 'mobile'}
            if self.landline_pattern:
                if re.match(self.landline_pattern, digits):
                    return {'valid': True, 'type': 'landline'}
            return {'valid': False, 'type': None}
        except Exception as e:
            logger.error(f"Phone validation error: {e}")
            return {'valid': False, 'type': None}
