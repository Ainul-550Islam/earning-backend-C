# api/models.py — cross-app import stubs

try:
    from api.security.models import DeviceInfo, SecurityLog, UserBan, RiskScore
except ImportError:
    class DeviceInfo: pass
    class SecurityLog: pass
    class UserBan: pass
    class RiskScore: pass

try:
    from api.wallet.models.core import Wallet, WalletTransaction
except ImportError:
    class Wallet: pass
    class WalletTransaction: pass

try:
    from api.notifications.models import Notice
except ImportError:
    class Notice: pass
