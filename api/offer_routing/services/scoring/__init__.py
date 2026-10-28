"""scoring service package."""

# Auto-generated stubs for missing exports
try:
    from offer_routing.services.scoring.OfferScorer import OfferScorer as OfferScoringService
except Exception:
    OfferScoringService = None
try:
    from offer_routing.services.scoring.OfferRanker import OfferRanker as OfferRankerService
except Exception:
    OfferRankerService = None
try:
    scoring_service = OfferScoringService() if OfferScoringService else None
except Exception:
    scoring_service = None
try:
    ranker_service = OfferRankerService() if OfferRankerService else None
except Exception:
    ranker_service = None
