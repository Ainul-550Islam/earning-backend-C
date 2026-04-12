# kyc/throttling.py  ── WORLD #1
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class KYCSubmitThrottle(UserRateThrottle):
    scope = 'kyc_submit'
    rate  = '5/hour'


class KYCFraudCheckThrottle(UserRateThrottle):
    scope = 'kyc_fraud_check'
    rate  = '10/hour'


class KYCStatusThrottle(UserRateThrottle):
    scope = 'kyc_status'
    rate  = '60/minute'


class KYCAdminThrottle(UserRateThrottle):
    scope = 'kyc_admin'
    rate  = '1000/hour'


class KYCExportThrottle(UserRateThrottle):
    scope = 'kyc_export'
    rate  = '10/day'
