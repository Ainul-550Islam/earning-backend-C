"""
api/ad_networks/signals_cap.py
Capitalized signal definitions for ad networks module
SaaS-ready with tenant support
"""

import django.dispatch

# Custom signals for ad networks module (Capitalized)

# Offer-related signals
OfferCreated = django.dispatch.Signal()
OfferUpdated = django.dispatch.Signal()
OfferActivated = django.dispatch.Signal()
OfferExpired = django.dispatch.Signal()

# Conversion-related signals
ConversionCreated = django.dispatch.Signal()
ConversionApproved = django.dispatch.Signal()
ConversionRejected = django.dispatch.Signal()
ConversionFlaggedAsFraud = django.dispatch.Signal()
ConversionChargeback = django.dispatch.Signal()

# Reward-related signals
RewardCreated = django.dispatch.Signal()
RewardApproved = django.dispatch.Signal()
RewardPaid = django.dispatch.Signal()
RewardCancelled = django.dispatch.Signal()

# User-related signals
UserEngagementCreated = django.dispatch.Signal()
UserEngagementCompleted = django.dispatch.Signal()
UserConversionCreated = django.dispatch.Signal()
UserRewardEarned = django.dispatch.Signal()

# Network-related signals
NetworkCreated = django.dispatch.Signal()
NetworkUpdated = django.dispatch.Signal()
NetworkHealthCheck = django.dispatch.Signal()
NetworkSyncCompleted = django.dispatch.Signal()
NetworkSyncFailed = django.dispatch.Signal()

# Fraud-related signals
FraudDetected = django.dispatch.Signal()
FraudScoreUpdated = django.dispatch.Signal()
SuspiciousActivityDetected = django.dispatch.Signal()
SecurityAlertTriggered = django.dispatch.Signal()

# Analytics signals
OfferClicked = django.dispatch.Signal()
OfferViewed = django.dispatch.Signal()
ConversionTracked = django.dispatch.Signal()
EngagementTracked = django.dispatch.Signal()

# System signals
CacheCleared = django.dispatch.Signal()
DataExported = django.dispatch.Signal()
ReportGenerated = django.dispatch.Signal()
NotificationSent = django.dispatch.Signal()

# WebSocket signals
WebSocketConnected = django.dispatch.Signal()
WebSocketDisconnected = django.dispatch.Signal()
MessageReceived = django.dispatch.Signal()
BroadcastSent = django.dispatch.Signal()

# Task-related signals
TaskStarted = django.dispatch.Signal()
TaskCompleted = django.dispatch.Signal()
TaskFailed = django.dispatch.Signal()
TaskRetry = django.dispatch.Signal()

# Integration signals
ExternalApiCall = django.dispatch.Signal()
WebhookReceived = django.dispatch.Signal()
SyncOperationCompleted = django.dispatch.Signal()
SyncOperationFailed = django.dispatch.Signal()

# Export all capitalized signals
__all__ = [
    # Offer signals
    'OfferCreated',
    'OfferUpdated', 
    'OfferActivated',
    'OfferExpired',
    
    # Conversion signals
    'ConversionCreated',
    'ConversionApproved',
    'ConversionRejected',
    'ConversionFlaggedAsFraud',
    'ConversionChargeback',
    
    # Reward signals
    'RewardCreated',
    'RewardApproved',
    'RewardPaid',
    'RewardCancelled',
    
    # User signals
    'UserEngagementCreated',
    'UserEngagementCompleted',
    'UserConversionCreated',
    'UserRewardEarned',
    
    # Network signals
    'NetworkCreated',
    'NetworkUpdated',
    'NetworkHealthCheck',
    'NetworkSyncCompleted',
    'NetworkSyncFailed',
    
    # Fraud signals
    'FraudDetected',
    'FraudScoreUpdated',
    'SuspiciousActivityDetected',
    'SecurityAlertTriggered',
    
    # Analytics signals
    'OfferClicked',
    'OfferViewed',
    'ConversionTracked',
    'EngagementTracked',
    
    # System signals
    'CacheCleared',
    'DataExported',
    'ReportGenerated',
    'NotificationSent',
    
    # WebSocket signals
    'WebSocketConnected',
    'WebSocketDisconnected',
    'MessageReceived',
    'BroadcastSent',
    
    # Task signals
    'TaskStarted',
    'TaskCompleted',
    'TaskFailed',
    'TaskRetry',
    
    # Integration signals
    'ExternalApiCall',
    'WebhookReceived',
    'SyncOperationCompleted',
    'SyncOperationFailed'
]
