"""
Advertiser Portal Models

This module contains all models for the advertiser portal.
"""
# Base classes from the flat models.py file (sibling to this package)
# We import them via a direct module reference to avoid the package shadowing the file
import importlib
_flat = importlib.import_module('api.advertiser_portal.models_base')
AdvertiserPortalBaseModel = _flat.AdvertiserPortalBaseModel
StatusModel = _flat.StatusModel
AuditModel = _flat.AuditModel
APIKeyModel = _flat.APIKeyModel
BudgetModel = _flat.BudgetModel
GeoModel = _flat.GeoModel
TrackingModel = _flat.TrackingModel
ConfigurationModel = _flat.ConfigurationModel
TimeStampedModel = _flat.TimeStampedModel
SoftDeleteModel = _flat.SoftDeleteModel
UUIDModel = _flat.UUIDModel

# Import all models to ensure Django discovers them
from .advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification, AdvertiserAgreement
from .campaign import AdCampaign, CampaignCreative, CampaignTargeting, CampaignBid, CampaignSchedule
from .offer import AdvertiserOffer, OfferRequirement, OfferCreative, OfferBlacklist
from .tracking import TrackingPixel, S2SPostback, Conversion, ConversionEvent, TrackingDomain
from .billing import AdvertiserWallet, AdvertiserTransaction, AdvertiserDeposit, AdvertiserInvoice, CampaignSpend, BillingAlert
from .reporting import AdvertiserReport, CampaignReport, PublisherBreakdown, GeoBreakdown, CreativePerformance
from .fraud_protection import ConversionQualityScore, AdvertiserFraudConfig, InvalidClickLog, ClickFraudSignal, OfferQualityScore, RoutingBlacklist
from .notification import AdvertiserNotification, AdvertiserAlert, NotificationTemplate
from .ml import UserJourneyStep, NetworkPerformanceCache, MLModel, MLPrediction

# Explicitly list all model names for Django's model discovery
# This ensures Django recognizes all models for makemigrations and migrate commands
__all__ = [
    # Advertiser models
    'Advertiser',
    'AdvertiserProfile',
    'AdvertiserVerification',
    'AdvertiserAgreement',
    
    # Campaign models
    'AdCampaign',
    'CampaignCreative',
    'CampaignTargeting',
    'CampaignBid',
    'CampaignSchedule',
    
    # Offer models
    'AdvertiserOffer',
    'OfferRequirement',
    'OfferCreative',
    'OfferBlacklist',
    
    # Tracking models
    'TrackingPixel',
    'S2SPostback',
    'Conversion',
    'ConversionEvent',
    'TrackingDomain',
    
    # Billing models
    'AdvertiserWallet',
    'AdvertiserTransaction',
    'AdvertiserDeposit',
    'AdvertiserInvoice',
    'CampaignSpend',
    'BillingAlert',
    
    # Reporting models
    'AdvertiserReport',
    'CampaignReport',
    'PublisherBreakdown',
    'GeoBreakdown',
    'CreativePerformance',
    
    # Fraud protection models
    'ConversionQualityScore',
    'AdvertiserFraudConfig',
    'InvalidClickLog',
    'ClickFraudSignal',
    'OfferQualityScore',
    'RoutingBlacklist',
    
    # Notification models
    'AdvertiserNotification',
    'AdvertiserAlert',
    'NotificationTemplate',
    
    # ML models
    'UserJourneyStep',
    'NetworkPerformanceCache',
    'MLModel',
    'MLPrediction',
]

# Django will discover models through the app registry
# The models will be available for makemigrations and migrate commands
# when Django apps are loaded properly.
