# api/payment_gateways/enums.py
from enum import Enum


class GatewayRegion(str, Enum):
    BD     = 'BD'
    GLOBAL = 'GLOBAL'
    US     = 'US'


class TransactionStatus(str, Enum):
    PENDING    = 'pending'
    PROCESSING = 'processing'
    COMPLETED  = 'completed'
    FAILED     = 'failed'
    CANCELLED  = 'cancelled'
    REVERSED   = 'reversed'
    ON_HOLD    = 'on_hold'


class PayoutStatus(str, Enum):
    PENDING    = 'pending'
    APPROVED   = 'approved'
    PROCESSING = 'processing'
    COMPLETED  = 'completed'
    REJECTED   = 'rejected'
    FAILED     = 'failed'


class FraudAction(str, Enum):
    ALLOW  = 'allow'
    FLAG   = 'flag'
    VERIFY = 'verify'
    BLOCK  = 'block'


class RiskLevel(str, Enum):
    LOW      = 'low'
    MEDIUM   = 'medium'
    HIGH     = 'high'
    CRITICAL = 'critical'


class ScheduleType(str, Enum):
    DAILY  = 'daily'
    WEEKLY = 'weekly'
    NET15  = 'net15'
    NET30  = 'net30'
    MANUAL = 'manual'


class HealthStatus(str, Enum):
    HEALTHY  = 'healthy'
    DEGRADED = 'degraded'
    DOWN     = 'down'
    TIMEOUT  = 'timeout'
    UNKNOWN  = 'unknown'


# Helper maps
RISK_THRESHOLDS = {
    RiskLevel.LOW:      (0,  30),
    RiskLevel.MEDIUM:   (31, 60),
    RiskLevel.HIGH:     (61, 80),
    RiskLevel.CRITICAL: (81, 100),
}

FRAUD_ACTIONS = {
    RiskLevel.LOW:      FraudAction.ALLOW,
    RiskLevel.MEDIUM:   FraudAction.FLAG,
    RiskLevel.HIGH:     FraudAction.VERIFY,
    RiskLevel.CRITICAL: FraudAction.BLOCK,
}
