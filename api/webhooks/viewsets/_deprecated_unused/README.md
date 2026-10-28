# Deprecated — not imported anywhere

These 5 files each duplicate a class that is also defined in `webhooks/views.py`.
`urls.py` routes the `views.py` versions, so these copies were dead code — never
imported by `viewsets/__init__.py`, `urls.py`, or anything else.

Moved here (instead of deleted) on 2026-07-23 during the independent code audit,
following the project's backup-before-replace convention. Safe to delete once
confirmed unneeded, or safe to restore if `views.py` is ever refactored to import
from here instead.

Classes: EventTypeListAPIView, WebhookDeliveryLogViewSet, WebhookEmitAPIView,
WebhookEndpointViewSet, WebhookSubscriptionViewSet.
