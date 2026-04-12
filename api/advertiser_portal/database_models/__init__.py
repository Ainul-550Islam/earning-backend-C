"""
Database Models Package

This package contains all database models for the Advertiser Portal.
"""

# Import all models for easy access
from .advertiser_model import *
from .campaign_model import *
from .creative_model import *
from .targeting_model import *
from .impression_model import *
from .click_model import *
from .conversion_model import *
from .billing_model import *
from .analytics_model import *
from .fraud_detection_model import *
from .ab_testing_model import *
from .integration_model import *
from .reporting_model import *
from .notification_model import *
from .user_model import *
from .audit_model import *
from .configuration_model import *

# Export model lists
__all__ = [
    # Advertiser Models
    'Advertiser',
    'AdvertiserVerification',
    'AdvertiserCredit',
    
    # Campaign Models
    'Campaign',
    'CampaignSpend',
    'CampaignGroup',
    
    # Creative Models
    'Creative',
    'CreativeAsset',
    'CreativeApprovalLog',
    
    # Targeting Models
    'Targeting',
    'AudienceSegment',
    'TargetingRule',
    
    # Impression Models
    'Impression',
    'ImpressionAggregation',
    'ImpressionPixel',
    
    # Click Models
    'Click',
    'ClickAggregation',
    'ClickPixel',
    
    # Conversion Models
    'Conversion',
    'ConversionAggregation',
    'ConversionPath',
    
    # Billing Models
    'BillingProfile',
    'PaymentMethod',
    'Invoice',
    'PaymentTransaction',
    
    # Analytics Models
    'AnalyticsReport',
    'AnalyticsMetric',
    'AnalyticsDashboard',
    'AnalyticsAlert',
    'AnalyticsDataPoint',
    
    # Fraud Detection Models
    'FraudDetectionRule',
    'FraudDetectionAlert',
    'FraudDetectionLog',
    'FraudDetectionReport',
    
    # A/B Testing Models
    'ABTest',
    'ABTestVariant',
    'ABTestResult',
    'ABTestInsight',
    
    # Integration Models
    'Integration',
    'IntegrationLog',
    'IntegrationWebhook',
    'IntegrationMapping',
    'IntegrationCredential',
    
    # Reporting Models
    'Report',
    'Dashboard',
    'Widget',
    'ReportTemplate',
    'ReportSchedule',
    
    # Notification Models
    'Notification',
    'NotificationTemplate',
    'NotificationPreference',
    'NotificationLog',
    
    # User Models
    'AdvertiserUser',
    'UserSession',
    'UserActivityLog',
    
    # Audit Models
    'AuditLog',
    'ComplianceReport',
    'RetentionPolicy',
    
    # Configuration Models
    'Configuration',
    'FeatureFlag',
    'SystemSetting',
    'ThemeConfiguration',
]
