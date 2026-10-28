# api/referral/viewsets.py
# Top-level viewsets re-export for DRF router registration
# Use this file in your router config:
#   from api.referral.viewsets import *
# ============================================================

from api.referral.viewsets.ReferralViewSet import ReferralStatsView, MyReferralsView, ReferralEarningsView, ReferralLeaderboardView
from api.referral.viewsets.ReferralCodeViewSet import ReferralCodeViewSet, ReferralCodeDetailView
from api.referral.viewsets.ReferralTreeViewSet import ReferralTreeViewSet
from api.referral.viewsets.CommissionLogViewSet import CommissionLogViewSet
from api.referral.viewsets.CommissionPayoutViewSet import CommissionPayoutViewSet
from api.referral.viewsets.ReferralCampaignViewSet import ReferralCampaignViewSet
from api.referral.viewsets.ReferralContestViewSet import ReferralContestViewSet
from api.referral.viewsets.ReferralFraudViewSet import ReferralFraudViewSet
from api.referral.viewsets.TopReferrerViewSet import TopReferrerViewSet
from api.referral.viewsets.ReferralInsightViewSet import ReferralInsightViewSet
from api.referral.viewsets.ReferralLTVViewSet import ReferralLTVViewSet
from api.referral.viewsets.AdminReferralViewSet import AdminReferralViewSet
from api.referral.viewsets.ReferralSettingsViewSet import ReferralSettingsViewSet