"""
Validators for Advertiser Portal

This module contains validation classes for validating data
before processing or storing in the database.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import UUID
import re
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from django.conf import settings
from django.utils import timezone

from .models import *
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .database_models import Advertiser
    from .schemas import *
    from .exceptions import *


class BaseValidator:
    """Base validator with common validation methods."""
    
    def validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Validate required fields are present and not empty.
        
        Args:
            data: Data to validate
            required_fields: List of required field names
            
        Raises:
            ValidationError: If required field is missing or empty
        """
        missing_fields = []
        
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                missing_fields.append(field)
        
        if missing_fields:
            raise ValidationError(f"Required fields are missing: {', '.join(missing_fields)}")
    
    def validate_string_length(self, value: str, min_length: int = 0, max_length: int = 255, 
                              field_name: str = 'field') -> None:
        """
        Validate string length.
        
        Args:
            value: String value to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length
            field_name: Name of the field for error messages
            
        Raises:
            ValidationError: If string length is invalid
        """
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")
        
        if len(value) < min_length:
            raise ValidationError(f"{field_name} must be at least {min_length} characters long")
        
        if len(value) > max_length:
            raise ValidationError(f"{field_name} must not exceed {max_length} characters")
    
    def validate_email(self, email: str, field_name: str = 'email') -> None:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
            field_name: Name of the field for error messages
            
        Raises:
            ValidationError: If email is invalid
        """
        try:
            EmailValidator()(email)
        except ValidationError:
            raise ValidationError(f"{field_name} is not a valid email address")
    
    def validate_url(self, url: str, field_name: str = 'url') -> None:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            field_name: Name of the field for error messages
            
        Raises:
            ValidationError: If URL is invalid
        """
        try:
            URLValidator()(url)
        except ValidationError:
            raise ValidationError(f"{field_name} is not a valid URL")
    
    def validate_phone(self, phone: str, field_name: str = 'phone') -> None:
        """
        Validate phone number format.
        
        Args:
            phone: Phone number to validate
            field_name: Name of the field for error messages
            
        Raises:
            ValidationError: If phone number is invalid
        """
        # Basic phone validation - can be enhanced based on requirements
        phone_pattern = re.compile(r'^\+?1?\d{9,15}$')
        if not phone_pattern.match(phone.replace('-', '').replace(' ', '')):
            raise ValidationError(f"{field_name} is not a valid phone number")
    
    def validate_decimal_range(self, value: Decimal, min_value: Optional[Decimal] = None,
                              max_value: Optional[Decimal] = None, 
                              field_name: str = 'field') -> None:
        """
        Validate decimal value range.
        
        Args:
            value: Decimal value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            field_name: Name of the field for error messages
            
        Raises:
            ValidationError: If value is out of range
        """
        if not isinstance(value, Decimal):
            raise ValidationError(f"{field_name} must be a valid number")
        
        if min_value is not None and value < min_value:
            raise ValidationError(f"{field_name} must be at least {min_value}")
        
        if max_value is not None and value > max_value:
            raise ValidationError(f"{field_name} must not exceed {max_value}")
    
    def validate_date_range(self, start_date: date, end_date: Optional[date] = None,
                           field_prefix: str = '') -> None:
        """
        Validate date range.
        
        Args:
            start_date: Start date
            end_date: End date (optional)
            field_prefix: Prefix for field names in error messages
            
        Raises:
            ValidationError: If date range is invalid
        """
        if start_date < timezone.now().date():
            raise ValidationError(f"{field_prefix}start date cannot be in the past")
        
        if end_date and end_date < start_date:
            raise ValidationError(f"{field_prefix}end date must be after start date")
    
    def validate_uuid(self, value: str, field_name: str = 'id') -> None:
        """
        Validate UUID format.
        
        Args:
            value: UUID string to validate
            field_name: Name of the field for error messages
            
        Raises:
            ValidationError: If UUID is invalid
        """
        try:
            UUID(value)
        except ValueError:
            raise ValidationError(f"{field_name} is not a valid UUID")


class AdvertiserValidator(BaseValidator):
    """Validator for advertiser data."""
    
    def validate_create_data(self, data: Dict[str, Any]) -> None:
        """
        Validate advertiser creation data.
        
        Args:
            data: Advertiser data to validate
            
        Raises:
            AdvertiserValidationError: If data is invalid
        """
        try:
            # Required fields
            required_fields = ['company_name', 'industry', 'contact_email']
            self.validate_required_fields(data, required_fields)
            
            # Validate company name
            self.validate_string_length(
                data['company_name'],
                min_length=2,
                max_length=255,
                field_name='company_name'
            )
            
            # Validate industry
            self.validate_string_length(
                data['industry'],
                min_length=2,
                max_length=100,
                field_name='industry'
            )
            
            # Validate email
            self.validate_email(data['contact_email'], 'contact_email')
            
            # Validate optional fields
            if 'website' in data and data['website']:
                self.validate_url(data['website'], 'website')
            
            if 'contact_phone' in data and data['contact_phone']:
                self.validate_phone(data['contact_phone'], 'contact_phone')
            
            if 'description' in data and data['description']:
                self.validate_string_length(
                    data['description'],
                    max_length=1000,
                    field_name='description'
                )
            
            # Check if company name already exists
            if Advertiser.objects.filter(
                company_name=data['company_name'],
                is_deleted=False
            ).exists():
                raise ValidationError("Company name already exists")
            
            # Check if email already exists
            if Advertiser.objects.filter(
                contact_email=data['contact_email'],
                is_deleted=False
            ).exists():
                raise ValidationError("Contact email already exists")
                
        except ValidationError as e:
            raise AdvertiserValidationError(str(e))
    
    def validate_update_data(self, data: Dict[str, Any]) -> None:
        """
        Validate advertiser update data.
        
        Args:
            data: Advertiser update data
            
        Raises:
            AdvertiserValidationError: If data is invalid
        """
        try:
            # Validate optional fields if provided
            if 'company_name' in data:
                self.validate_string_length(
                    data['company_name'],
                    min_length=2,
                    max_length=255,
                    field_name='company_name'
                )
            
            if 'industry' in data:
                self.validate_string_length(
                    data['industry'],
                    min_length=2,
                    max_length=100,
                    field_name='industry'
                )
            
            if 'contact_email' in data:
                self.validate_email(data['contact_email'], 'contact_email')
            
            if 'website' in data and data['website']:
                self.validate_url(data['website'], 'website')
            
            if 'contact_phone' in data and data['contact_phone']:
                self.validate_phone(data['contact_phone'], 'contact_phone')
            
            if 'description' in data and data['description']:
                self.validate_string_length(
                    data['description'],
                    max_length=1000,
                    field_name='description'
                )
                
        except ValidationError as e:
            raise AdvertiserValidationError(str(e))


class CampaignValidator(BaseValidator):
    """Validator for campaign data."""
    
    def validate_create_data(self, data: Dict[str, Any], advertiser: "Advertiser") -> None:
        """
        Validate campaign creation data.
        
        Args:
            data: Campaign data to validate
            advertiser: "Advertiser" instance
            
        Raises:
            CampaignValidationError: If data is invalid
        """
        try:
            # Required fields
            required_fields = ['name', 'objective', 'daily_budget', 'total_budget', 'start_date']
            self.validate_required_fields(data, required_fields)
            
            # Validate campaign name
            self.validate_string_length(
                data['name'],
                min_length=2,
                max_length=255,
                field_name='campaign name'
            )
            
            # Validate objective
            valid_objectives = [choice[0] for choice in CampaignObjectiveEnum]
            if data['objective'] not in valid_objectives:
                raise ValidationError(f"Invalid objective. Must be one of: {', '.join(valid_objectives)}")
            
            # Validate budgets
            self.validate_decimal_range(
                data['daily_budget'],
                min_value=Decimal('0.01'),
                field_name='daily_budget'
            )
            
            self.validate_decimal_range(
                data['total_budget'],
                min_value=Decimal('0.01'),
                field_name='total_budget'
            )
            
            if data['total_budget'] < data['daily_budget']:
                raise ValidationError("Total budget must be greater than or equal to daily budget")
            
            # Validate dates
            self.validate_date_range(data['start_date'], data.get('end_date'))
            
            # Validate bidding strategy
            if 'bidding_strategy' in data:
                valid_strategies = [choice[0] for choice in BiddingStrategyEnum]
                if data['bidding_strategy'] not in valid_strategies:
                    raise ValidationError(f"Invalid bidding strategy. Must be one of: {', '.join(valid_strategies)}")
            
            # Validate target CPA/ROAS if provided
            if 'target_cpa' in data and data['target_cpa']:
                self.validate_decimal_range(
                    data['target_cpa'],
                    min_value=Decimal('0.01'),
                    field_name='target_cpa'
                )
            
            if 'target_roas' in data and data['target_roas']:
                self.validate_decimal_range(
                    data['target_roas'],
                    min_value=Decimal('0.01'),
                    field_name='target_roas'
                )
            
            # Check advertiser limits
            self._validate_advertiser_limits(advertiser)
                
        except ValidationError as e:
            raise CampaignValidationError(str(e))
    
    def _validate_advertiser_limits(self, advertiser: "Advertiser") -> None:
        """Validate advertiser campaign limits."""
        # Check if advertiser has reached maximum campaigns limit
        max_campaigns = getattr(settings, 'MAX_CAMPAIGNS_PER_ADVERTISER', 100)
        current_campaigns = Campaign.objects.filter(
            advertiser=advertiser,
            is_deleted=False
        ).count()
        
        if current_campaigns >= max_campaigns:
            raise ValidationError(f"Advertiser has reached maximum campaign limit of {max_campaigns}")
    
    def validate_budget_update(self, campaign: "Campaign", daily_budget: Optional[Decimal] = None,
                             total_budget: Optional[Decimal] = None) -> None:
        """
        Validate budget update.
        
        Args:
            campaign: "Campaign" instance
            daily_budget: New daily budget
            total_budget: New total budget
            
        Raises:
            CampaignValidationError: If budget update is invalid
        """
        try:
            if daily_budget is not None:
                self.validate_decimal_range(
                    daily_budget,
                    min_value=Decimal('0.01'),
                    field_name='daily_budget'
                )
            
            if total_budget is not None:
                if total_budget < campaign.current_spend:
                    raise ValidationError("Total budget cannot be less than current spend")
                
                self.validate_decimal_range(
                    total_budget,
                    min_value=Decimal('0.01'),
                    field_name='total_budget'
                )
                
                if daily_budget and total_budget < daily_budget:
                    raise ValidationError("Total budget must be greater than or equal to daily budget")
                    
        except ValidationError as e:
            raise CampaignValidationError(str(e))


class CreativeValidator(BaseValidator):
    """Validator for creative data."""
    
    def validate_create_data(self, data: Dict[str, Any], campaign: "Campaign") -> None:
        """
        Validate creative creation data.
        
        Args:
            data: Creative data to validate
            campaign: "Campaign" instance
            
        Raises:
            CreativeValidationError: If data is invalid
        """
        try:
            # Required fields
            required_fields = ['name', 'type', 'landing_page_url']
            self.validate_required_fields(data, required_fields)
            
            # Validate creative name
            self.validate_string_length(
                data['name'],
                min_length=2,
                max_length=255,
                field_name='creative name'
            )
            
            # Validate creative type
            valid_types = [choice[0] for choice in CreativeTypeEnum]
            if data['type'] not in valid_types:
                raise ValidationError(f"Invalid creative type. Must be one of: {', '.join(valid_types)}")
            
            # Validate landing page URL
            self.validate_url(data['landing_page_url'], 'landing_page_url')
            
            # Validate optional fields
            if 'title' in data and data['title']:
                self.validate_string_length(
                    data['title'],
                    max_length=255,
                    field_name='title'
                )
            
            if 'description' in data and data['description']:
                self.validate_string_length(
                    data['description'],
                    max_length=500,
                    field_name='description'
                )
            
            if 'tracking_url' in data and data['tracking_url']:
                self.validate_url(data['tracking_url'], 'tracking_url')
            
            # Validate creative data based on type
            self._validate_creative_type_data(data)
            
            # Check campaign creative limits
            self._validate_campaign_creative_limits(campaign)
                
        except ValidationError as e:
            raise CreativeValidationError(str(e))
    
    def _validate_creative_type_data(self, data: Dict[str, Any]) -> None:
        """Validate creative data based on creative type."""
        creative_type = data.get('type')
        creative_data = data.get('creative_data', {})
        
        if creative_type == CreativeTypeEnum.BANNER.value:
            # Banner creatives should have dimensions
            if not creative_data.get('width') or not creative_data.get('height'):
                raise ValidationError("Banner creatives must have width and height")
        
        elif creative_type == CreativeTypeEnum.VIDEO.value:
            # Video creatives should have duration
            if not creative_data.get('duration'):
                raise ValidationError("Video creatives must have duration")
        
        elif creative_type == CreativeTypeEnum.HTML5.value:
            # HTML5 creatives should have HTML content
            if not creative_data.get('html_content'):
                raise ValidationError("HTML5 creatives must have HTML content")
    
    def _validate_campaign_creative_limits(self, campaign: "Campaign") -> None:
        """Validate campaign creative limits."""
        max_creatives = getattr(settings, 'MAX_CREATIVES_PER_CAMPAIGN', 50)
        current_creatives = Creative.objects.filter(
            campaign=campaign,
            is_deleted=False
        ).count()
        
        if current_creatives >= max_creatives:
            raise ValidationError(f"Campaign has reached maximum creative limit of {max_creatives}")


class TargetingValidator(BaseValidator):
    """Validator for targeting data."""
    
    def validate_create_data(self, data: Dict[str, Any], campaign: "Campaign") -> None:
        """
        Validate targeting creation data.
        
        Args:
            data: Targeting data to validate
            campaign: "Campaign" instance
            
        Raises:
            TargetingValidationError: If data is invalid
        """
        try:
            # Required fields
            required_fields = ['geo_targeting', 'device_targeting']
            self.validate_required_fields(data, required_fields)
            
            # Validate geo targeting
            self._validate_geo_targeting(data['geo_targeting'])
            
            # Validate device targeting
            self._validate_device_targeting(data['device_targeting'])
            
            # Validate age range
            if 'age_min' in data and data['age_min']:
                self._validate_age(data['age_min'], data.get('age_max'))
            
            # Validate lists
            list_fields = ['genders', 'languages', 'interests', 'keywords', 'exclude_keywords']
            for field in list_fields:
                if field in data and data[field]:
                    self._validate_string_list(data[field], field)
                    
        except ValidationError as e:
            raise TargetingValidationError(str(e))
    
    def _validate_geo_targeting(self, geo_targeting: Dict[str, Any]) -> None:
        """Validate geo targeting configuration."""
        if not isinstance(geo_targeting, dict):
            raise ValidationError("Geo targeting must be a dictionary")
        
        # Validate countries if provided
        if 'countries' in geo_targeting and geo_targeting['countries']:
            if not isinstance(geo_targeting['countries'], list):
                raise ValidationError("Countries must be a list")
            
            for country in geo_targeting['countries']:
                if not isinstance(country, str) or len(country) != 2:
                    raise ValidationError("Country codes must be 2-character ISO codes")
        
        # Validate coordinates if provided
        if 'latitude' in geo_targeting or 'longitude' in geo_targeting:
            if not geo_targeting.get('latitude') or not geo_targeting.get('longitude'):
                raise ValidationError("Both latitude and longitude must be provided for coordinate targeting")
            
            lat = geo_targeting['latitude']
            lon = geo_targeting['longitude']
            
            if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
                raise ValidationError("Latitude must be between -90 and 90")
            
            if not isinstance(lon, (int, float)) or not (-180 <= lon <= 180):
                raise ValidationError("Longitude must be between -180 and 180")
            
            # Validate radius if provided
            if 'radius' in geo_targeting and geo_targeting['radius']:
                if not isinstance(geo_targeting['radius'], int) or geo_targeting['radius'] <= 0:
                    raise ValidationError("Radius must be a positive integer")
    
    def _validate_device_targeting(self, device_targeting: Dict[str, Any]) -> None:
        """Validate device targeting configuration."""
        if not isinstance(device_targeting, dict):
            raise ValidationError("Device targeting must be a dictionary")
        
        # Validate device types if provided
        if 'device_types' in device_targeting and device_targeting['device_types']:
            if not isinstance(device_targeting['device_types'], list):
                raise ValidationError("Device types must be a list")
            
            valid_device_types = [choice[0] for choice in DeviceTypeEnum]
            for device_type in device_targeting['device_types']:
                if device_type not in valid_device_types:
                    raise ValidationError(f"Invalid device type: {device_type}")
        
        # Validate OS families if provided
        if 'os_families' in device_targeting and device_targeting['os_families']:
            if not isinstance(device_targeting['os_families'], list):
                raise ValidationError("OS families must be a list")
            
            valid_os_families = [choice[0] for choice in OSFamilyEnum]
            for os_family in device_targeting['os_families']:
                if os_family not in valid_os_families:
                    raise ValidationError(f"Invalid OS family: {os_family}")
    
    def _validate_age(self, age_min: Optional[int], age_max: Optional[int]) -> None:
        """Validate age range."""
        if age_min and not isinstance(age_min, int):
            raise ValidationError("Age minimum must be an integer")
        
        if age_max and not isinstance(age_max, int):
            raise ValidationError("Age maximum must be an integer")
        
        if age_min and (age_min < 13 or age_min > 65):
            raise ValidationError("Age minimum must be between 13 and 65")
        
        if age_max and (age_max < 13 or age_max > 65):
            raise ValidationError("Age maximum must be between 13 and 65")
        
        if age_min and age_max and age_min > age_max:
            raise ValidationError("Age minimum cannot be greater than age maximum")
    
    def _validate_string_list(self, value: List[str], field_name: str) -> None:
        """Validate string list."""
        if not isinstance(value, list):
            raise ValidationError(f"{field_name} must be a list")
        
        for item in value:
            if not isinstance(item, str):
                raise ValidationError(f"All items in {field_name} must be strings")
            
            if len(item.strip()) == 0:
                raise ValidationError(f"{field_name} cannot contain empty strings")


class BillingValidator(BaseValidator):
    """Validator for billing data."""
    
    def validate_payment_data(self, data: Dict[str, Any]) -> None:
        """
        Validate payment data.
        
        Args:
            data: Payment data to validate
            
        Raises:
            BillingValidationError: If data is invalid
        """
        try:
            # Required fields
            required_fields = ['amount', 'payment_method_id']
            self.validate_required_fields(data, required_fields)
            
            # Validate amount
            if not isinstance(data['amount'], (int, float, Decimal)):
                raise ValidationError("Amount must be a valid number")
            
            amount = Decimal(str(data['amount']))
            self.validate_decimal_range(
                amount,
                min_value=Decimal('0.01'),
                max_value=Decimal('999999.99'),
                field_name='amount'
            )
            
            # Validate payment method ID
            self.validate_uuid(data['payment_method_id'], 'payment_method_id')
                
        except ValidationError as e:
            raise BillingValidationError(str(e))
    
    def validate_invoice_data(self, data: Dict[str, Any]) -> None:
        """
        Validate invoice data.
        
        Args:
            data: Invoice data to validate
            
        Raises:
            BillingValidationError: If data is invalid
        """
        try:
            # Required fields
            required_fields = ['invoice_number', 'issue_date', 'due_date', 'total_amount']
            self.validate_required_fields(data, required_fields)
            
            # Validate invoice number
            self.validate_string_length(
                data['invoice_number'],
                min_length=1,
                max_length=50,
                field_name='invoice_number'
            )
            
            # Validate dates
            self.validate_date_range(data['issue_date'], data['due_date'], 'invoice_')
            
            # Validate amounts
            self.validate_decimal_range(
                data['total_amount'],
                min_value=Decimal('0.01'),
                field_name='total_amount'
            )
            
            if 'tax_amount' in data and data['tax_amount']:
                self.validate_decimal_range(
                    data['tax_amount'],
                    min_value=Decimal('0'),
                    field_name='tax_amount'
                )
                
        except ValidationError as e:
            raise BillingValidationError(str(e))


# Additional Validators for Main Models
class OfferValidator(BaseValidator):
    """Validator for offer data."""
    
    def validate_offer_data(self, data: Dict[str, Any]) -> None:
        """
        Validate offer data.
        
        Args:
            data: Offer data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['name', 'advertiser', 'offer_type', 'pricing_model', 'payout_amount']
            self.validate_required_fields(data, required_fields)
            
            # Validate name
            self.validate_string_field(
                data['name'],
                min_length=1,
                max_length=200,
                field_name='name'
            )
            
            # Validate payout amount
            self.validate_decimal_range(
                data['payout_amount'],
                min_value=Decimal('0.01'),
                max_value=Decimal('10000'),
                field_name='payout_amount'
            )
            
            # Validate dates
            if 'start_date' in data and data['start_date']:
                if 'end_date' in data and data['end_date']:
                    self.validate_date_range(data['start_date'], data['end_date'], 'offer_')
            
            # Validate landing page URL
            if 'landing_page' in data and data['landing_page']:
                self.validate_url(data['landing_page'], 'landing_page')
                
        except ValidationError as e:
            raise ValidationError(f"Offer validation failed: {str(e)}")


class TrackingValidator(BaseValidator):
    """Validator for tracking data."""
    
    def validate_tracking_pixel_data(self, data: Dict[str, Any]) -> None:
        """
        Validate tracking pixel data.
        
        Args:
            data: Tracking pixel data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['name', 'advertiser', 'pixel_type']
            self.validate_required_fields(data, required_fields)
            
            # Validate name
            self.validate_string_field(
                data['name'],
                min_length=1,
                max_length=100,
                field_name='name'
            )
            
            # Validate pixel type
            valid_pixel_types = ['conversion', 'impression', 'click', 'postback']
            if data['pixel_type'] not in valid_pixel_types:
                raise ValidationError(f"Invalid pixel type. Must be one of: {', '.join(valid_pixel_types)}")
            
            # Validate URLs
            if 'url' in data and data['url']:
                self.validate_url(data['url'], 'url')
            
            if 'postback_url' in data and data['postback_url']:
                self.validate_url(data['postback_url'], 'postback_url')
                
        except ValidationError as e:
            raise ValidationError(f"Tracking pixel validation failed: {str(e)}")
    
    def validate_conversion_data(self, data: Dict[str, Any]) -> None:
        """
        Validate conversion data.
        
        Args:
            data: Conversion data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['advertiser', 'offer', 'revenue']
            self.validate_required_fields(data, required_fields)
            
            # Validate revenue
            self.validate_decimal_range(
                data['revenue'],
                min_value=Decimal('0'),
                max_value=Decimal('10000'),
                field_name='revenue'
            )
            
            # Validate IP address
            if 'ip_address' in data and data['ip_address']:
                self.validate_ip_address(data['ip_address'])
                
        except ValidationError as e:
            raise ValidationError(f"Conversion validation failed: {str(e)}")


class FraudValidator(BaseValidator):
    """Validator for fraud detection data."""
    
    def validate_conversion_quality_score(self, data: Dict[str, Any]) -> None:
        """
        Validate conversion quality score data.
        
        Args:
            data: Quality score data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate score ranges
            score_fields = ['overall_score', 'behavioral_score', 'technical_score', 'timing_score', 'engagement_score']
            
            for field in score_fields:
                if field in data and data[field] is not None:
                    if not (0 <= float(data[field]) <= 1):
                        raise ValidationError(f"{field} must be between 0 and 1")
            
            # Validate quality level
            if 'quality_level' in data and data['quality_level']:
                valid_levels = ['high', 'medium', 'low', 'invalid']
                if data['quality_level'] not in valid_levels:
                    raise ValidationError(f"Invalid quality level. Must be one of: {', '.join(valid_levels)}")
                    
        except ValidationError as e:
            raise ValidationError(f"Quality score validation failed: {str(e)}")
    
    def validate_fraud_config(self, data: Dict[str, Any]) -> None:
        """
        Validate fraud configuration data.
        
        Args:
            data: Fraud config data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate config name
            if 'config_name' in data and data['config_name']:
                self.validate_string_field(
                    data['config_name'],
                    min_length=1,
                    max_length=100,
                    field_name='config_name'
                )
            
            # Validate rules
            if 'rules' in data and data['rules']:
                if not isinstance(data['rules'], dict):
                    raise ValidationError("Rules must be a dictionary")
            
            # Validate thresholds
            if 'thresholds' in data and data['thresholds']:
                if not isinstance(data['thresholds'], dict):
                    raise ValidationError("Thresholds must be a dictionary")
                    
        except ValidationError as e:
            raise ValidationError(f"Fraud config validation failed: {str(e)}")


class NotificationValidator(BaseValidator):
    """Validator for notification data."""
    
    def validate_notification_data(self, data: Dict[str, Any]) -> None:
        """
        Validate notification data.
        
        Args:
            data: Notification data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['advertiser', 'notification_type', 'title', 'message']
            self.validate_required_fields(data, required_fields)
            
            # Validate title
            self.validate_string_field(
                data['title'],
                min_length=1,
                max_length=200,
                field_name='title'
            )
            
            # Validate message
            self.validate_string_field(
                data['message'],
                min_length=1,
                max_length=1000,
                field_name='message'
            )
            
            # Validate notification type
            valid_types = ['info', 'warning', 'error', 'success', 'billing', 'campaign', 'offer']
            if data['notification_type'] not in valid_types:
                raise ValidationError(f"Invalid notification type. Must be one of: {', '.join(valid_types)}")
            
            # Validate priority
            if 'priority' in data and data['priority']:
                valid_priorities = ['low', 'medium', 'high', 'urgent']
                if data['priority'] not in valid_priorities:
                    raise ValidationError(f"Invalid priority. Must be one of: {', '.join(valid_priorities)}")
                    
        except ValidationError as e:
            raise ValidationError(f"Notification validation failed: {str(e)}")
    
    def validate_notification_template(self, data: Dict[str, Any]) -> None:
        """
        Validate notification template data.
        
        Args:
            data: Template data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['template_type', 'name', 'subject', 'body_template']
            self.validate_required_fields(data, required_fields)
            
            # Validate name
            self.validate_string_field(
                data['name'],
                min_length=1,
                max_length=100,
                field_name='name'
            )
            
            # Validate subject
            self.validate_string_field(
                data['subject'],
                min_length=1,
                max_length=200,
                field_name='subject'
            )
            
            # Validate body template
            self.validate_string_field(
                data['body_template'],
                min_length=1,
                max_length=2000,
                field_name='body_template'
            )
            
            # Validate template type
            valid_types = ['email', 'sms', 'push', 'in_app']
            if data['template_type'] not in valid_types:
                raise ValidationError(f"Invalid template type. Must be one of: {', '.join(valid_types)}")
                    
        except ValidationError as e:
            raise ValidationError(f"Template validation failed: {str(e)}")


class MLValidator(BaseValidator):
    """Validator for ML model data."""
    
    def validate_ml_model_data(self, data: Dict[str, Any]) -> None:
        """
        Validate ML model data.
        
        Args:
            data: ML model data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['name', 'model_type', 'version']
            self.validate_required_fields(data, required_fields)
            
            # Validate name
            self.validate_string_field(
                data['name'],
                min_length=1,
                max_length=100,
                field_name='name'
            )
            
            # Validate version
            self.validate_string_field(
                data['version'],
                min_length=1,
                max_length=20,
                field_name='version'
            )
            
            # Validate model type
            valid_types = ['classification', 'regression', 'clustering', 'anomaly_detection', 'recommendation']
            if data['model_type'] not in valid_types:
                raise ValidationError(f"Invalid model type. Must be one of: {', '.join(valid_types)}")
            
            # Validate status
            if 'status' in data and data['status']:
                valid_statuses = ['training', 'trained', 'active', 'inactive', 'failed']
                if data['status'] not in valid_statuses:
                    raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
                    
        except ValidationError as e:
            raise ValidationError(f"ML model validation failed: {str(e)}")
    
    def validate_ml_prediction_data(self, data: Dict[str, Any]) -> None:
        """
        Validate ML prediction data.
        
        Args:
            data: Prediction data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['model', 'input_data', 'prediction']
            self.validate_required_fields(data, required_fields)
            
            # Validate confidence score
            if 'confidence_score' in data and data['confidence_score'] is not None:
                if not (0 <= float(data['confidence_score']) <= 1):
                    raise ValidationError("Confidence score must be between 0 and 1")
            
            # Validate input data
            if not isinstance(data['input_data'], dict):
                raise ValidationError("Input data must be a dictionary")
                    
        except ValidationError as e:
            raise ValidationError(f"ML prediction validation failed: {str(e)}")


class ReportValidator(BaseValidator):
    """Validator for report data."""
    
    def validate_report_data(self, data: Dict[str, Any]) -> None:
        """
        Validate report data.
        
        Args:
            data: Report data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['advertiser', 'report_type', 'title']
            self.validate_required_fields(data, required_fields)
            
            # Validate title
            self.validate_string_field(
                data['title'],
                min_length=1,
                max_length=200,
                field_name='title'
            )
            
            # Validate report type
            valid_types = ['campaign', 'offer', 'billing', 'conversion', 'fraud', 'performance']
            if data['report_type'] not in valid_types:
                raise ValidationError(f"Invalid report type. Must be one of: {', '.join(valid_types)}")
            
            # Validate date range
            if 'start_date' in data and data['start_date']:
                if 'end_date' in data and data['end_date']:
                    self.validate_date_range(data['start_date'], data['end_date'], 'report_')
                    
        except ValidationError as e:
            raise ValidationError(f"Report validation failed: {str(e)}")


class WalletValidator(BaseValidator):
    """Validator for wallet data."""
    
    def validate_wallet_data(self, data: Dict[str, Any]) -> None:
        """
        Validate wallet data.
        
        Args:
            data: Wallet data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate balance
            if 'balance' in data and data['balance'] is not None:
                if float(data['balance']) < 0:
                    raise ValidationError("Balance cannot be negative")
            
            # Validate currency
            if 'currency' in data and data['currency']:
                valid_currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY']
                if data['currency'] not in valid_currencies:
                    raise ValidationError(f"Invalid currency. Must be one of: {', '.join(valid_currencies)}")
            
            # Validate auto refill settings
            if 'auto_refill_enabled' in data and data['auto_refill_enabled']:
                if 'auto_refill_threshold' in data and data['auto_refill_threshold']:
                    self.validate_decimal_range(
                        data['auto_refill_threshold'],
                        min_value=Decimal('0'),
                        field_name='auto_refill_threshold'
                    )
                
                if 'auto_refill_amount' in data and data['auto_refill_amount']:
                    self.validate_decimal_range(
                        data['auto_refill_amount'],
                        min_value=Decimal('1'),
                        field_name='auto_refill_amount'
                    )
                    
        except ValidationError as e:
            raise ValidationError(f"Wallet validation failed: {str(e)}")


class TransactionValidator(BaseValidator):
    """Validator for transaction data."""
    
    def validate_transaction_data(self, data: Dict[str, Any]) -> None:
        """
        Validate transaction data.
        
        Args:
            data: Transaction data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            required_fields = ['wallet', 'transaction_type', 'amount']
            self.validate_required_fields(data, required_fields)
            
            # Validate amount
            self.validate_decimal_range(
                data['amount'],
                min_value=Decimal('0.01'),
                max_value=Decimal('100000'),
                field_name='amount'
            )
            
            # Validate transaction type
            valid_types = ['deposit', 'withdrawal', 'spend', 'refund', 'bonus', 'penalty']
            if data['transaction_type'] not in valid_types:
                raise ValidationError(f"Invalid transaction type. Must be one of: {', '.join(valid_types)}")
            
            # Validate status
            if 'status' in data and data['status']:
                valid_statuses = ['pending', 'processing', 'completed', 'failed', 'cancelled']
                if data['status'] not in valid_statuses:
                    raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
                    
        except ValidationError as e:
            raise ValidationError(f"Transaction validation failed: {str(e)}")


# Validator Factory
class ValidatorFactory:
    """Factory class for creating validator instances."""
    
    _validators = {
        'advertiser': AdvertiserValidator,
        'campaign': CampaignValidator,
        'creative': CreativeValidator,
        'targeting': TargetingValidator,
        'billing': BillingValidator,
        'offer': OfferValidator,
        'tracking': TrackingValidator,
        'fraud': FraudValidator,
        'notification': NotificationValidator,
        'ml': MLValidator,
        'report': ReportValidator,
        'wallet': WalletValidator,
        'transaction': TransactionValidator,
    }
    
    @classmethod
    def get_validator(cls, name: str) -> BaseValidator:
        """
        Get validator instance by name.
        
        Args:
            name: Validator name
            
        Returns:
            Validator instance
        """
        if name not in cls._validators:
            raise ValueError(f"Unknown validator: {name}")
        
        return cls._validators[name]()
    
    @classmethod
    def register_validator(cls, name: str, validator_class: type) -> None:
        """
        Register a new validator.
        
        Args:
            name: Validator name
            validator_class: Validator class
        """
        cls._validators[name] = validator_class
