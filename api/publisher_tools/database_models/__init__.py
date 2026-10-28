# publisher_tools/database_models/__init__.py
"""
⚠️  DEPRECATED — database_models/ সম্পূর্ণ অব্যবহৃত (orphaned)।

এই subfolder-এর সব 21টি class হুবহু analytics_warehouse/models.py-এর
duplicate। কোথাও import করা হয় না, কোনো migration নেই, কোনো DB table নেই।

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  সমাধান: analytics_warehouse ব্যবহার করো।
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

আগে যদি database_models থেকে import করতে:
  ❌  from publisher_tools.database_models import PublisherRecord

এখন analytics_warehouse থেকে করো:
  ✅  from analytics_warehouse.models import PublisherRecord

Migration guide (class mapping):
  database_models class           →  analytics_warehouse class
  ────────────────────────────────────────────────────────
  PublisherRecord                 →  PublisherRecord
  SiteRecord                      →  SiteRecord
  AppRecord                       →  AppRecord
  AdUnitRecord                    →  AdUnitRecord
  ImpressionRecord                →  ImpressionRecord
  ClickRecord                     →  ClickRecord
  RevenueRecord                   →  RevenueRecord
  InvoiceRecord                   →  InvoiceRecord
  PaymentRecord                   →  PaymentRecord
  FraudLogRecord                  →  FraudLogRecord
  AuditLogRecord                  →  AuditLogRecord
  AdPlacementRecord               →  AdPlacementRecord
  ReportRecord                    →  ReportRecord
  AlertRecord                     →  AlertRecord
  WebhookLogRecord                →  WebhookLogRecord
  NotificationRecord              →  NotificationRecord
  SettingRecord                   →  SettingRecord
  APIKeyLogRecord                 →  APIKeyLogRecord
  OptimizationLogRecord           →  OptimizationLogRecord
  ABTestRecord                    →  ABTestRecord
  WarehouseRecordMixin            →  (analytics_warehouse base mixin — internal)

এই folder টি পরবর্তী major release-এ DELETE করা হবে।
তার আগে এই folder-এর কোনো class নতুন কোডে ব্যবহার করো না।

পদক্ষেপ:
  1. analytics_warehouse migration চালাও:
       python manage.py migrate analytics_warehouse --database=analytics

  2. project/urls.py-তে warehouse URL যোগ করো:
       path('api/warehouse/', include('analytics_warehouse.urls'))

  3. settings.py-তে নিশ্চিত করো:
       INSTALLED_APPS  += ['analytics_warehouse']
       DATABASE_ROUTERS = ['analytics_warehouse.db_router.AnalyticsRouter']
       DATABASES['analytics'] = {
           'ENGINE':   'django.db.backends.postgresql',
           'NAME':     'analytics_warehouse',
           'USER':     '...',
           'PASSWORD': '...',
           'HOST':     '...',
           'PORT':     '5432',
       }

  4. এই database_models/ folder টি ব্যবহার বন্ধ করো।
"""

import warnings

warnings.warn(
    "publisher_tools.database_models is DEPRECATED and will be removed. "
    "Use analytics_warehouse.models instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ── Backward compatibility shim ───────────────────────────────────────────────
# যদি কোনো পুরনো code এখনো database_models থেকে import করে,
# তাহলে analytics_warehouse থেকে re-export করে দেওয়া হচ্ছে।
# এটি শুধু migration period-এর জন্য।

try:
    from analytics_warehouse.models import (
        PublisherRecord,
        SiteRecord,
        AppRecord,
        AdUnitRecord,
        ImpressionRecord,
        ClickRecord,
        RevenueRecord,
        InvoiceRecord,
        PaymentRecord,
        FraudLogRecord,
        AuditLogRecord,
        AdPlacementRecord,
        ReportRecord,
        AlertRecord,
        WebhookLogRecord,
        NotificationRecord,
        SettingRecord,
        APIKeyLogRecord,
        OptimizationLogRecord,
        ABTestRecord,
    )

    __all__ = [
        'PublisherRecord', 'SiteRecord', 'AppRecord', 'AdUnitRecord',
        'ImpressionRecord', 'ClickRecord', 'RevenueRecord',
        'InvoiceRecord', 'PaymentRecord', 'FraudLogRecord',
        'AuditLogRecord', 'AdPlacementRecord', 'ReportRecord',
        'AlertRecord', 'WebhookLogRecord', 'NotificationRecord',
        'SettingRecord', 'APIKeyLogRecord', 'OptimizationLogRecord',
        'ABTestRecord',
    ]

except ImportError:
    # analytics_warehouse এখনো install না হলে graceful fallback
    __all__ = []
