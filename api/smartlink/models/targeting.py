from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _
from .smartlink import SmartLink
from ..choices import (
    TargetingMode, DeviceType, OSType, BrowserType, DayOfWeek
)


class TargetingRule(models.Model):
    """
    Master targeting rule set for a SmartLink.
    Combines all targeting sub-rules with AND/OR logic.
    """
    smartlink = models.OneToOneField(
        SmartLink, on_delete=models.CASCADE,
        related_name='targeting_rule',
    )
    logic = models.CharField(
        max_length=3,
        choices=[('AND', 'All rules must match'), ('OR', 'Any rule must match')],
        default='AND',
        verbose_name=_('Rule Logic')
    )
    is_active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(
        default=0,
        help_text=_('Higher priority rules evaluated first.')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_targeting_rule'
        verbose_name = _('Targeting Rule')

    def __str__(self):
        return f"TargetingRule: {self.smartlink.slug} ({self.logic})"


class GeoTargeting(models.Model):
    """
    Country/region/city whitelist or blacklist.
    Whitelist: only allow listed countries.
    Blacklist: allow all except listed countries.
    """
    rule = models.OneToOneField(
        TargetingRule, on_delete=models.CASCADE,
        related_name='geo_targeting',
    )
    mode = models.CharField(
        max_length=10,
        choices=TargetingMode.choices,
        default=TargetingMode.WHITELIST,
    )
    countries = ArrayField(
        models.CharField(max_length=2),
        default=list,
        blank=True,
        help_text=_('ISO 3166-1 alpha-2 country codes. e.g. ["BD","US","GB"]')
    )
    regions = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text=_('Region/state names.')
    )
    cities = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_geo_targeting'
        verbose_name = _('Geo Targeting')

    def __str__(self):
        return f"Geo [{self.mode}]: {', '.join(self.countries[:5])}"

    def matches(self, country: str, region: str = '', city: str = '') -> bool:
        """Check if a given geo matches this rule."""
        if not self.countries and not self.regions and not self.cities:
            return True  # No restrictions = allow all

        in_list = (
            country.upper() in [c.upper() for c in self.countries] or
            (region and any(r.lower() in region.lower() for r in self.regions)) or
            (city and any(c.lower() in city.lower() for c in self.cities))
        )
        if self.mode == TargetingMode.WHITELIST:
            return in_list
        else:  # BLACKLIST
            return not in_list


class DeviceTargeting(models.Model):
    """Mobile/tablet/desktop device type targeting."""
    rule = models.OneToOneField(
        TargetingRule, on_delete=models.CASCADE,
        related_name='device_targeting',
    )
    mode = models.CharField(max_length=10, choices=TargetingMode.choices, default=TargetingMode.WHITELIST)
    device_types = ArrayField(
        models.CharField(max_length=10, choices=DeviceType.choices),
        default=list,
        blank=True,
        help_text=_('e.g. ["mobile", "tablet"]')
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_device_targeting'
        verbose_name = _('Device Targeting')

    def __str__(self):
        return f"Device [{self.mode}]: {self.device_types}"

    def matches(self, device_type: str) -> bool:
        if not self.device_types:
            return True
        in_list = device_type.lower() in [d.lower() for d in self.device_types]
        return in_list if self.mode == TargetingMode.WHITELIST else not in_list


class OSTargeting(models.Model):
    """Operating system targeting: Android, iOS, Windows, Mac, Linux."""
    rule = models.OneToOneField(
        TargetingRule, on_delete=models.CASCADE,
        related_name='os_targeting',
    )
    mode = models.CharField(max_length=10, choices=TargetingMode.choices, default=TargetingMode.WHITELIST)
    os_types = ArrayField(
        models.CharField(max_length=10, choices=OSType.choices),
        default=list,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_os_targeting'
        verbose_name = _('OS Targeting')

    def matches(self, os_type: str) -> bool:
        if not self.os_types:
            return True
        in_list = os_type.lower() in [o.lower() for o in self.os_types]
        return in_list if self.mode == TargetingMode.WHITELIST else not in_list


class BrowserTargeting(models.Model):
    """Browser targeting: Chrome, Firefox, Safari, Edge."""
    rule = models.OneToOneField(
        TargetingRule, on_delete=models.CASCADE,
        related_name='browser_targeting',
    )
    mode = models.CharField(max_length=10, choices=TargetingMode.choices, default=TargetingMode.WHITELIST)
    browsers = ArrayField(
        models.CharField(max_length=10, choices=BrowserType.choices),
        default=list,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_browser_targeting'
        verbose_name = _('Browser Targeting')

    def matches(self, browser: str) -> bool:
        if not self.browsers:
            return True
        in_list = browser.lower() in [b.lower() for b in self.browsers]
        return in_list if self.mode == TargetingMode.WHITELIST else not in_list


class TimeTargeting(models.Model):
    """
    Day of week and hour of day targeting.
    Example: Mon-Fri, 9:00-17:00 only.
    """
    rule = models.OneToOneField(
        TargetingRule, on_delete=models.CASCADE,
        related_name='time_targeting',
    )
    days_of_week = ArrayField(
        models.IntegerField(choices=DayOfWeek.choices),
        default=list,
        blank=True,
        help_text=_('0=Monday, 6=Sunday. Empty = all days.')
    )
    start_hour = models.PositiveSmallIntegerField(
        default=0,
        help_text=_('UTC hour to start (0-23).')
    )
    end_hour = models.PositiveSmallIntegerField(
        default=23,
        help_text=_('UTC hour to end (0-23).')
    )
    timezone_name = models.CharField(
        max_length=50, default='UTC',
        help_text=_('Timezone for day/hour evaluation.')
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_time_targeting'
        verbose_name = _('Time Targeting')

    def matches(self, day_of_week: int, hour: int) -> bool:
        """Check if current day/hour matches this rule."""
        if self.days_of_week and day_of_week not in self.days_of_week:
            return False
        return self.start_hour <= hour <= self.end_hour


class ISPTargeting(models.Model):
    """
    Carrier/ISP whitelist targeting.
    Useful for mobile carrier-specific offers (e.g., Grameenphone BD).
    """
    rule = models.OneToOneField(
        TargetingRule, on_delete=models.CASCADE,
        related_name='isp_targeting',
    )
    mode = models.CharField(max_length=10, choices=TargetingMode.choices, default=TargetingMode.WHITELIST)
    isps = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text=_('ISP/carrier names. e.g. ["Grameenphone","Robi","Banglalink"]')
    )
    asns = ArrayField(
        models.CharField(max_length=20),
        default=list,
        blank=True,
        help_text=_('ASN numbers. e.g. ["AS24389", "AS17494"]')
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_isp_targeting'
        verbose_name = _('ISP Targeting')

    def matches(self, isp_name: str = '', asn: str = '') -> bool:
        if not self.isps and not self.asns:
            return True
        in_list = (
            any(isp.lower() in isp_name.lower() for isp in self.isps) or
            (asn and asn in self.asns)
        )
        return in_list if self.mode == TargetingMode.WHITELIST else not in_list


class LanguageTargeting(models.Model):
    """Browser language targeting (from Accept-Language header)."""
    rule = models.OneToOneField(
        TargetingRule, on_delete=models.CASCADE,
        related_name='language_targeting',
    )
    mode = models.CharField(max_length=10, choices=TargetingMode.choices, default=TargetingMode.WHITELIST)
    languages = ArrayField(
        models.CharField(max_length=10),
        default=list,
        blank=True,
        help_text=_('ISO 639-1 language codes. e.g. ["en","bn","ar"]')
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_language_targeting'
        verbose_name = _('Language Targeting')

    def matches(self, language: str) -> bool:
        if not self.languages:
            return True
        in_list = language.lower() in [lang.lower() for lang in self.languages]
        return in_list if self.mode == TargetingMode.WHITELIST else not in_list
