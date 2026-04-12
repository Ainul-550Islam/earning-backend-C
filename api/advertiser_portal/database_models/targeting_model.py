"""
Targeting Database Model

This module contains the Targeting model and related models
for managing campaign targeting configurations.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.gis.geos import GEOSGeometry


from ..models import *
from ..enums import *
from ..utils import *
from ..validators import *


class Targeting(AdvertiserPortalBaseModel, AuditModel):
    """
    Main targeting model for managing campaign targeting configurations.
    
    This model stores all targeting settings including geographic,
    demographic, device, and behavioral targeting options.
    """
    
    # Basic Information
    campaign = models.OneToOneField(
        'advertiser_portal.Campaign',
        on_delete=models.CASCADE,
        related_name='targeting',
        help_text="Associated campaign"
    )
    name = models.CharField(
        max_length=255,
        help_text="Targeting configuration name"
    )
    description = models.TextField(
        blank=True,
        help_text="Targeting configuration description"
    )
    
    # Geographic Targeting
    geo_targeting_type = models.CharField(
        max_length=20,
        choices=[
            ('countries', 'Countries'),
            ('regions', 'Regions'),
            ('cities', 'Cities'),
            ('postal_codes', 'Postal Codes'),
            ('coordinates', 'Coordinates'),
            ('radius', 'Radius')
        ],
        default='countries',
        help_text="Type of geographic targeting"
    )
    countries = models.JSONField(
        default=list,
        blank=True,
        help_text="List of country codes (ISO 3166-1 alpha-2)"
    )
    regions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of regions/states"
    )
    cities = models.JSONField(
        default=list,
        blank=True,
        help_text="List of cities"
    )
    postal_codes = models.JSONField(
        default=list,
        blank=True,
        help_text="List of postal codes"
    )
    geo_coordinates = models.JSONField(null=True, blank=True, help_text="Geographic coordinates as {lat, lng}")
    geo_radius = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Radius in kilometers for coordinate targeting"
    )
    geo_shapes = models.JSONField(null=True, blank=True, help_text="Geographic shapes as GeoJSON")
    
    # Device Targeting
    device_types = models.JSONField(
        default=list,
        blank=True,
        help_text="List of device types to target"
    )
    os_families = models.JSONField(
        default=list,
        blank=True,
        help_text="List of OS families to target"
    )
    os_versions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of OS versions to target"
    )
    browsers = models.JSONField(
        default=list,
        blank=True,
        help_text="List of browsers to target"
    )
    carriers = models.JSONField(
        default=list,
        blank=True,
        help_text="List of mobile carriers to target"
    )
    device_models = models.JSONField(
        default=list,
        blank=True,
        help_text="List of specific device models to target"
    )
    
    # Demographic Targeting
    age_min = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(13), MaxValueValidator(65)],
        help_text="Minimum age to target"
    )
    age_max = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(13), MaxValueValidator(65)],
        help_text="Maximum age to target"
    )
    genders = models.JSONField(
        default=list,
        blank=True,
        help_text="List of genders to target"
    )
    household_income = models.JSONField(
        default=dict,
        blank=True,
        help_text="Household income targeting settings"
    )
    education_levels = models.JSONField(
        default=list,
        blank=True,
        help_text="List of education levels to target"
    )
    marital_status = models.JSONField(
        default=list,
        blank=True,
        help_text="List of marital statuses to target"
    )
    parental_status = models.JSONField(
        default=list,
        blank=True,
        help_text="List of parental statuses to target"
    )
    
    # Behavioral Targeting
    interests = models.JSONField(
        default=list,
        blank=True,
        help_text="List of interest categories"
    )
    behaviors = models.JSONField(
        default=list,
        blank=True,
        help_text="List of behavioral segments"
    )
    purchase_history = models.JSONField(
        default=dict,
        blank=True,
        help_text="Purchase history targeting settings"
    )
    website_visitors = models.JSONField(
        default=dict,
        blank=True,
        help_text="Website visitor targeting settings"
    )
    app_users = models.JSONField(
        default=dict,
        blank=True,
        help_text="App user targeting settings"
    )
    
    # Contextual Targeting
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="List of keywords to target"
    )
    exclude_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="List of keywords to exclude"
    )
    topics = models.JSONField(
        default=list,
        blank=True,
        help_text="List of topics to target"
    )
    categories = models.JSONField(
        default=list,
        blank=True,
        help_text="List of content categories"
    )
    placements = models.JSONField(
        default=list,
        blank=True,
        help_text="List of specific placements"
    )
    
    # Language and Location
    languages = models.JSONField(
        default=list,
        blank=True,
        help_text="List of languages to target"
    )
    locations = models.JSONField(
        default=list,
        blank=True,
        help_text="List of location types to target"
    )
    
    # Time-based Targeting
    dayparting = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dayparting settings by hour"
    )
    day_of_week = models.JSONField(
        default=list,
        blank=True,
        help_text="Days of week to target [1-7]"
    )
    holidays = models.JSONField(
        default=list,
        blank=True,
        help_text="Holiday targeting settings"
    )
    seasons = models.JSONField(
        default=list,
        blank=True,
        help_text="Seasonal targeting settings"
    )
    
    # Advanced Targeting
    lookalike_audiences = models.JSONField(
        default=list,
        blank=True,
        help_text="List of lookalike audiences"
    )
    custom_audiences = models.JSONField(
        default=list,
        blank=True,
        help_text="List of custom audiences"
    )
    remarketing_audiences = models.JSONField(
        default=list,
        blank=True,
        help_text="List of remarketing audiences"
    )
    exclusion_audiences = models.JSONField(
        default=list,
        blank=True,
        help_text="List of audiences to exclude"
    )
    
    # Frequency and Reach
    frequency_cap = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum impressions per user"
    )
    frequency_cap_period = models.CharField(
        max_length=20,
        choices=[
            ('hourly', 'Per Hour'),
            ('daily', 'Per Day'),
            ('weekly', 'Per Week'),
            ('monthly', 'Per Month'),
            ('campaign', 'Per Campaign')
        ],
        null=True,
        blank=True,
        help_text="Frequency cap period"
    )
    reach_estimate = models.BigIntegerField(
        default=0,
        help_text="Estimated reach of this targeting"
    )
    
    # Quality and Performance
    targeting_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Targeting quality score (0-100)"
    )
    performance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Targeting performance score (0-100)"
    )
    
    # Settings and Configuration
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this targeting is active"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default targeting"
    )
    priority = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Targeting priority (1-10)"
    )
    
    # External Integrations
    external_targeting_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External targeting ID"
    )
    integration_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration settings"
    )
    
    class Meta:
        db_table = 'targeting'
        verbose_name = 'Targeting'
        verbose_name_plural = 'Targeting'
        indexes = [
            models.Index(fields=['campaign']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.campaign.name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate age range
        if self.age_min and self.age_max and self.age_min > self.age_max:
            raise ValidationError("Age minimum cannot be greater than age maximum")
        
        # Validate geographic targeting
        if self.geo_targeting_type == 'coordinates':
            if not self.geo_coordinates:
                raise ValidationError("Coordinates are required for coordinate targeting")
            if not self.geo_radius:
                raise ValidationError("Radius is required for coordinate targeting")
        
        # Validate frequency capping
        if self.frequency_cap and not self.frequency_cap_period:
            raise ValidationError("Frequency cap period is required when frequency cap is set")
        
        # Validate targeting lists
        if self.keywords and len(self.keywords) > 1000:
            raise ValidationError("Maximum 1000 keywords allowed")
        
        if self.exclude_keywords and len(self.exclude_keywords) > 500:
            raise ValidationError("Maximum 500 exclude keywords allowed")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Calculate reach estimate
        self.reach_estimate = self.calculate_reach_estimate()
        
        # Calculate targeting score
        self.targeting_score = self.calculate_targeting_score()
        
        super().save(*args, **kwargs)
    
    def calculate_reach_estimate(self) -> int:
        """Calculate estimated reach for this targeting configuration."""
        # Base reach (would typically come from audience data)
        base_reach = 1000000  # 1 million base audience
        
        # Apply geographic targeting
        if self.countries:
            geo_factor = len(self.countries) * 0.3  # Each country ~30% of base
        else:
            geo_factor = 1.0
        
        # Apply device targeting
        if self.device_types:
            device_factor = len(self.device_types) * 0.4  # Each device type ~40% of base
        else:
            device_factor = 1.0
        
        # Apply demographic targeting
        demo_factor = 1.0
        if self.age_min or self.age_max:
            demo_factor *= 0.6  # Age targeting reduces to 60%
        if self.genders:
            demo_factor *= 0.5  # Gender targeting reduces to 50%
        
        # Apply behavioral targeting
        if self.interests:
            interest_factor = max(0.1, 1.0 - (len(self.interests) * 0.05))
        else:
            interest_factor = 1.0
        
        # Calculate final reach
        estimated_reach = int(base_reach * geo_factor * device_factor * demo_factor * interest_factor)
        
        return max(1000, estimated_reach)  # Minimum 1000
    
    def calculate_targeting_score(self) -> Decimal:
        """Calculate targeting quality score."""
        score = 0
        
        # Geographic targeting (25 points)
        if self.countries:
            score += 15
        if self.regions or self.cities:
            score += 10
        
        # Device targeting (20 points)
        if self.device_types:
            score += 10
        if self.os_families:
            score += 10
        
        # Demographic targeting (20 points)
        if self.age_min or self.age_max:
            score += 10
        if self.genders:
            score += 10
        
        # Behavioral targeting (25 points)
        if self.interests:
            score += 15
        if self.keywords:
            score += 10
        
        # Advanced targeting (10 points)
        if self.custom_audiences or self.lookalike_audiences:
            score += 10
        
        return Decimal(str(min(score, 100)))
    
    def get_targeting_summary(self) -> Dict[str, Any]:
        """Get summary of all targeting settings."""
        return {
            'geographic': {
                'type': self.geo_targeting_type,
                'countries': self.countries,
                'regions': self.regions,
                'cities': self.cities,
                'postal_codes': self.postal_codes,
                'coordinates': {
                    'point': str(self.geo_coordinates) if self.geo_coordinates else None,
                    'radius': self.geo_radius
                } if self.geo_coordinates else None
            },
            'device': {
                'device_types': self.device_types,
                'os_families': self.os_families,
                'os_versions': self.os_versions,
                'browsers': self.browsers,
                'carriers': self.carriers,
                'device_models': self.device_models
            },
            'demographic': {
                'age_range': {
                    'min': self.age_min,
                    'max': self.age_max
                } if self.age_min or self.age_max else None,
                'genders': self.genders,
                'household_income': self.household_income,
                'education_levels': self.education_levels,
                'marital_status': self.marital_status,
                'parental_status': self.parental_status
            },
            'behavioral': {
                'interests': self.interests,
                'behaviors': self.behaviors,
                'purchase_history': self.purchase_history,
                'website_visitors': self.website_visitors,
                'app_users': self.app_users
            },
            'contextual': {
                'keywords': self.keywords,
                'exclude_keywords': self.exclude_keywords,
                'topics': self.topics,
                'categories': self.categories,
                'placements': self.placements
            },
            'language_location': {
                'languages': self.languages,
                'locations': self.locations
            },
            'time_based': {
                'dayparting': self.dayparting,
                'day_of_week': self.day_of_week,
                'holidays': self.holidays,
                'seasons': self.seasons
            },
            'advanced': {
                'lookalike_audiences': self.lookalike_audiences,
                'custom_audiences': self.custom_audiences,
                'remarketing_audiences': self.remarketing_audiences,
                'exclusion_audiences': self.exclusion_audiences
            },
            'frequency': {
                'cap': self.frequency_cap,
                'period': self.frequency_cap_period
            } if self.frequency_cap else None,
            'metrics': {
                'reach_estimate': self.reach_estimate,
                'targeting_score': float(self.targeting_score),
                'performance_score': float(self.performance_score)
            }
        }
    
    def validate_targeting(self) -> Dict[str, Any]:
        """Validate targeting configuration and return results."""
        errors = []
        warnings = []
        
        # Geographic validation
        if not self.countries and not self.regions and not self.cities:
            warnings.append("No geographic targeting specified - will target globally")
        
        if self.geo_coordinates and not self.geo_radius:
            errors.append("Radius is required when coordinates are specified")
        
        # Device validation
        if not self.device_types:
            warnings.append("No device targeting specified - will target all devices")
        
        # Demographic validation
        if self.age_min and self.age_max:
            age_range = self.age_max - self.age_min
            if age_range < 5:
                warnings.append("Very narrow age range may limit reach")
            elif age_range > 50:
                warnings.append("Very wide age range may reduce targeting precision")
        
        # Keyword validation
        if self.keywords and len(self.keywords) > 1000:
            errors.append("Too many keywords - maximum 1000 allowed")
        
        if self.exclude_keywords and len(self.exclude_keywords) > 500:
            errors.append("Too many exclude keywords - maximum 500 allowed")
        
        # Frequency capping validation
        if self.frequency_cap and self.frequency_cap < 1:
            errors.append("Frequency cap must be at least 1")
        
        # Audience validation
        total_audiences = (
            len(self.lookalike_audiences or []) +
            len(self.custom_audiences or []) +
            len(self.remarketing_audiences or [])
        )
        
        if total_audiences > 50:
            warnings.append("Too many audiences may impact performance")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_audience_overlap(self, other_targeting: 'Targeting') -> Dict[str, Any]:
        """Calculate audience overlap with another targeting configuration."""
        overlap_score = 0
        
        # Geographic overlap
        geo_overlap = 0
        if self.countries and other_targeting.countries:
            common_countries = set(self.countries) & set(other_targeting.countries)
            geo_overlap = len(common_countries) / max(len(self.countries), len(other_targeting.countries))
        
        # Device overlap
        device_overlap = 0
        if self.device_types and other_targeting.device_types:
            common_devices = set(self.device_types) & set(other_targeting.device_types)
            device_overlap = len(common_devices) / max(len(self.device_types), len(other_targeting.device_types))
        
        # Interest overlap
        interest_overlap = 0
        if self.interests and other_targeting.interests:
            common_interests = set(self.interests) & set(other_targeting.interests)
            interest_overlap = len(common_interests) / max(len(self.interests), len(other_targeting.interests))
        
        # Calculate overall overlap
        overlap_score = (geo_overlap + device_overlap + interest_overlap) / 3
        
        return {
            'overlap_score': overlap_score,
            'geo_overlap': geo_overlap,
            'device_overlap': device_overlap,
            'interest_overlap': interest_overlap,
            'recommendation': 'high' if overlap_score > 0.7 else 'medium' if overlap_score > 0.3 else 'low'
        }
    
    def expand_targeting(self, expansion_type: str = 'similar') -> Dict[str, Any]:
        """Get targeting expansion suggestions."""
        suggestions = []
        
        if expansion_type == 'similar':
            # Geographic expansion
            if self.countries:
                similar_countries = self._get_similar_countries(self.countries)
                if similar_countries:
                    suggestions.append({
                        'type': 'geographic_expansion',
                        'title': 'Expand Geographic Targeting',
                        'description': f'Consider adding similar countries: {", ".join(similar_countries[:3])}',
                        'suggested_changes': {
                            'countries': self.countries + similar_countries[:3]
                        }
                    })
            
            # Device expansion
            if self.device_types:
                all_devices = [choice[0] for choice in DeviceTypeEnum.choices]
                missing_devices = set(all_devices) - set(self.device_types)
                if missing_devices:
                    suggestions.append({
                        'type': 'device_expansion',
                        'title': 'Expand Device Targeting',
                        'description': f'Consider adding devices: {", ".join(list(missing_devices)[:3])}',
                        'suggested_changes': {
                            'device_types': self.device_types + list(missing_devices)[:3]
                        }
                    })
            
            # Interest expansion
            if self.interests:
                similar_interests = self._get_similar_interests(self.interests)
                if similar_interests:
                    suggestions.append({
                        'type': 'interest_expansion',
                        'title': 'Expand Interest Targeting',
                        'description': f'Consider adding similar interests: {", ".join(similar_interests[:5])}',
                        'suggested_changes': {
                            'interests': self.interests + similar_interests[:5]
                        }
                    })
        
        elif expansion_type == 'broader':
            # Broader targeting suggestions
            if self.age_min and self.age_max:
                age_range = self.age_max - self.age_min
                if age_range < 10:
                    suggestions.append({
                        'type': 'age_expansion',
                        'title': 'Expand Age Range',
                        'description': f'Consider expanding age range from {self.age_min}-{self.age_max} to {max(13, self.age_min - 5)}-{min(65, self.age_max + 5)}',
                        'suggested_changes': {
                            'age_min': max(13, self.age_min - 5),
                            'age_max': min(65, self.age_max + 5)
                        }
                    })
        
        return {
            'suggestions': suggestions,
            'expansion_type': expansion_type
        }
    
    def _get_similar_countries(self, countries: List[str]) -> List[str]:
        """Get similar countries based on geography/economy."""
        # Simplified similarity mapping
        similarity_map = {
            'US': ['CA', 'MX', 'GB', 'AU'],
            'GB': ['US', 'CA', 'IE', 'AU'],
            'DE': ['AT', 'CH', 'FR', 'NL'],
            'FR': ['DE', 'BE', 'CH', 'ES'],
            'JP': ['KR', 'TW', 'SG'],
            'AU': ['NZ', 'SG', 'JP']
        }
        
        similar = set()
        for country in countries:
            similar.update(similarity_map.get(country, []))
        
        return list(similar - set(countries))
    
    def _get_similar_interests(self, interests: List[str]) -> List[str]:
        """Get similar interests based on categories."""
        # Simplified interest similarity mapping
        similarity_map = {
            'technology': ['software', 'programming', 'gadgets', 'innovation'],
            'sports': ['fitness', 'outdoor', 'games', 'competition'],
            'entertainment': ['movies', 'music', 'television', 'celebrity'],
            'business': ['finance', 'marketing', 'entrepreneurship', 'investment'],
            'health': ['wellness', 'medical', 'fitness', 'nutrition'],
            'travel': ['vacation', 'tourism', 'adventure', 'destinations']
        }
        
        similar = set()
        for interest in interests:
            interest_lower = interest.lower()
            for category, similar_interests in similarity_map.items():
                if category in interest_lower:
                    similar.update(similar_interests)
        
        return list(similar - set(interests))


class AudienceSegment(AdvertiserPortalBaseModel):
    """
    Model for managing custom audience segments.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='audience_segments'
    )
    name = models.CharField(
        max_length=255,
        help_text="Segment name"
    )
    description = models.TextField(
        blank=True,
        help_text="Segment description"
    )
    segment_type = models.CharField(
        max_length=50,
        choices=[
            ('custom', 'Custom'),
            ('lookalike', 'Lookalike'),
            ('remarketing', 'Remarketing'),
            ('behavioral', 'Behavioral'),
            ('demographic', 'Demographic')
        ],
        default='custom',
        help_text="Type of audience segment"
    )
    criteria = models.JSONField(
        default=dict,
        help_text="Segment criteria"
    )
    user_count = models.IntegerField(
        default=0,
        help_text="Estimated user count in segment"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether segment is active"
    )
    
    class Meta:
        db_table = 'audience_segments'
        verbose_name = 'Audience Segment'
        verbose_name_plural = 'Audience Segments'
        unique_together = ['advertiser', 'name']
        indexes = [
            models.Index(fields=['advertiser', 'segment_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.advertiser.company_name})"


class TargetingRule(AdvertiserPortalBaseModel):
    """
    Model for managing targeting rules and logic.
    """
    
    targeting = models.ForeignKey(
        Targeting,
        on_delete=models.CASCADE,
        related_name='rules'
    )
    rule_type = models.CharField(
        max_length=50,
        choices=[
            ('include', 'Include'),
            ('exclude', 'Exclude'),
            ('bid_adjustment', 'Bid Adjustment')
        ],
        default='include',
        help_text="Type of targeting rule"
    )
    condition = models.CharField(
        max_length=50,
        choices=[
            ('equals', 'Equals'),
            ('not_equals', 'Not Equals'),
            ('contains', 'Contains'),
            ('not_contains', 'Not Contains'),
            ('greater_than', 'Greater Than'),
            ('less_than', 'Less Than'),
            ('between', 'Between'),
            ('in_list', 'In List'),
            ('not_in_list', 'Not In List')
        ],
        help_text="Rule condition"
    )
    field = models.CharField(
        max_length=100,
        help_text="Field to apply rule to"
    )
    value = models.JSONField(
        help_text="Rule value(s)"
    )
    bid_adjustment = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('10.00'))],
        help_text="Bid adjustment multiplier"
    )
    priority = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Rule priority (1-10)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether rule is active"
    )
    
    class Meta:
        db_table = 'targeting_rules'
        verbose_name = 'Targeting Rule'
        verbose_name_plural = 'Targeting Rules'
        indexes = [
            models.Index(fields=['targeting', 'rule_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self) -> str:
        return f"{self.field} {self.condition} {self.value}"
