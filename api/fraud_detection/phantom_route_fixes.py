# =============================================================================
# fraud_detection/phantom_route_fixes.py — DRY SHIM
# All phantom route fixes have been applied directly in views_extended.py.
# This file is kept for documentation only.
# =============================================================================
# Fixes applied in views_extended.py._patch_viewsets():
#   FraudPatternViewSet      → accuracy_stats
#   DeviceFingerprintViewSet → bulk_verify
#   IPReputationViewSet      → bulk_check, bulk_blacklist
#   OfferCompletionViewSet   → fraud_analysis
#   FraudCaseEvidenceViewSet → bulk_upload
#   FraudCaseActionViewSet   → bulk_create
