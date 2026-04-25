# api/payment_gateways/tests.py
# Root test file — imports all sub-module tests for discovery

# Gateway tests
from api.payment_gateways.tests.test_bkash      import *  # noqa
from api.payment_gateways.tests.test_nagad       import *  # noqa
from api.payment_gateways.tests.test_sslcommerz  import *  # noqa
from api.payment_gateways.tests.test_stripe      import *  # noqa
from api.payment_gateways.tests.test_paypal      import *  # noqa

# Service tests
from api.payment_gateways.tests.test_deposit_service     import *  # noqa
from api.payment_gateways.tests.test_withdrawal_service  import *  # noqa
from api.payment_gateways.tests.test_gateway_health      import *  # noqa
from api.payment_gateways.tests.test_gateway_router      import *  # noqa
from api.payment_gateways.tests.test_webhook_verifier    import *  # noqa
from api.payment_gateways.tests.test_reconciliation      import *  # noqa

# Integration tests
from api.payment_gateways.tests.test_integration         import *  # noqa
from api.payment_gateways.tests.test_performance         import *  # noqa
