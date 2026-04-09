# api/djoyalty/services/advanced/__init__.py
"""
Advanced services:
  CampaignService             : Active campaigns + multipliers + join
  LoyaltyFraudService         : Rapid txn check, daily redemption cap
  SubscriptionLoyaltyService  : Monthly subscription renewal + bonus
  InsightService              : Daily/weekly insight report generation
"""
from .CampaignService import CampaignService
from .LoyaltyFraudService import LoyaltyFraudService
from .SubscriptionLoyaltyService import SubscriptionLoyaltyService
from .InsightService import InsightService

__all__ = [
    'CampaignService', 'LoyaltyFraudService',
    'SubscriptionLoyaltyService', 'InsightService',
]
