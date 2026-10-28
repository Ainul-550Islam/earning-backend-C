# =============================================================================
# fraud_detection/detectors/__init__.py — CANONICAL EXPORTS
#
# Every detector class is exported here.
# Import pattern (DRY):
#   from api.fraud_detection.detectors import VelocityEngine, BaseDetector
# =============================================================================
from .BaseDetector              import BaseDetector
from .VelocityEngine            import VelocityEngine
from .BehavioralBiometricsAnalyzer import BehavioralBiometricsAnalyzer
from .ClickFraudDetector        import ClickFraudDetector
from .DeviceFingerprinter       import DeviceFingerprinter
from .GeoVelocityDetector       import GeoVelocityDetector
from .GraphNetworkAnalyzer      import GraphNetworkAnalyzer
from .MultiAccountDetector      import MultiAccountDetector
from .PatternAnalyzer           import PatternAnalyzer
from .ReferralFraudDetector     import ReferralFraudDetector
from .VPNProxyDetector          import VPNProxyDetector

# ── Registry: slug → class (used by views_detectors.py and detectors/urls.py) ─
DETECTOR_REGISTRY = {
    "velocity-engine":        VelocityEngine,
    "behavioral-biometrics":  BehavioralBiometricsAnalyzer,
    "click-fraud":            ClickFraudDetector,
    "device-fingerprinter":   DeviceFingerprinter,
    "geo-velocity":           GeoVelocityDetector,
    "graph-network":          GraphNetworkAnalyzer,
    "multi-account":          MultiAccountDetector,
    "pattern-analyzer":       PatternAnalyzer,
    "referral-fraud":         ReferralFraudDetector,
    "vpn-proxy":              VPNProxyDetector,
}

__all__ = [
    "BaseDetector",
    "VelocityEngine",
    "BehavioralBiometricsAnalyzer",
    "ClickFraudDetector",
    "DeviceFingerprinter",
    "GeoVelocityDetector",
    "GraphNetworkAnalyzer",
    "MultiAccountDetector",
    "PatternAnalyzer",
    "ReferralFraudDetector",
    "VPNProxyDetector",
    "DETECTOR_REGISTRY",
]
