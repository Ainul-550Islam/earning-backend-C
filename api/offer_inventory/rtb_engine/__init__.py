# api/offer_inventory/rtb_engine/__init__.py
"""
RTB Engine — Real-Time Bidding & Programmatic Advertising.
Handles bid requests, bid floor management, eCPM calculation,
demand-side platform (DSP) connections, and win/loss notifications.
This module makes the platform compete with IronSource, Unity Ads, Fyber.
"""
from .bid_processor      import BidProcessor, BidRequest, BidResponse
from .ecpm_calculator    import ECPMCalculator
from .bid_floor_manager  import BidFloorManager
from .dsp_connector      import DSPConnector
from .win_notifier       import WinNotifier

__all__ = [
    'BidProcessor', 'BidRequest', 'BidResponse',
    'ECPMCalculator', 'BidFloorManager', 'DSPConnector', 'WinNotifier',
]
