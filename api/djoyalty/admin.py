# api/djoyalty/admin.py
"""
Djoyalty Admin -- root-level convenience import।
All admin registrations are in djoyalty/admin/ package।
This file ensures Django discovers all admin classes।
"""
# Core admin
from .admin.customer_admin import *       # noqa
from .admin.points_admin import *         # noqa
from .admin.tier_admin import *           # noqa
from .admin.earn_rule_admin import *      # noqa
from .admin.redemption_admin import *     # noqa
from .admin.voucher_admin import *        # noqa
from .admin.badge_admin import *          # noqa
from .admin.campaign_admin import *       # noqa
from .admin.partner_admin import *        # noqa
from .admin.fraud_admin import *          # noqa
from .admin.insight_admin import *        # noqa

# New admin modules
try:
    from .admin.offerwall_admin import *  # noqa
except ImportError:
    pass

try:
    from .admin.notification_admin import *  # noqa
except ImportError:
    pass

try:
    from .admin.catalog_admin import *    # noqa
except ImportError:
    pass
