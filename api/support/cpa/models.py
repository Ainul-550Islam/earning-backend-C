"""
api/support/cpa/models.py
Compatibility shim. The models live in api.support.models.cpa; defining them
here as well would raise "Conflicting models" the first time this module loads.
"""
from api.support.models.cpa import (  # noqa: F401
    OfferDispute, NetworkAnnouncement, PublisherProfile,
)
