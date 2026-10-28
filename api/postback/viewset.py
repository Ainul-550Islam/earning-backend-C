"""
viewset.py – DEPRECATED. Do not import from this module.

All ViewSet definitions have been consolidated into viewsets.py which
is the only file registered in urls.py. This file is kept as a tombstone
to surface clear errors rather than silent import failures.

Previous contents:
  - BasePostbackViewSet    → see viewsets.py (inline per-viewset logic)
  - PostbackLogViewSet     → see viewsets.py :: PostbackLogViewSet
  - PostbackInsightViewSet → see viewsets.py :: PostbackInsightViewSet
  - NetworkPostbackConfigViewSet → see viewsets.py :: NetworkPostbackConfigViewSet
"""

raise ImportError(
    "viewset.py is deprecated. Import from postback.viewsets instead. "
    "See viewsets.py for the canonical, URL-registered ViewSet definitions."
)
