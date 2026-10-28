"""
viewsets_insight.py – DEPRECATED. Do not import from this module.

All ViewSet definitions have been consolidated into viewsets.py.
The richer analytics actions (summary, trends, network_comparison,
health_report) from this file have been merged into
PostbackInsightViewSet in viewsets.py.

Keeping this file as a tombstone avoids silent breakage from any
lingering imports in management commands or external scripts.
"""

raise ImportError(
    "viewsets_insight.py is deprecated. "
    "Import from postback.viewsets instead."
)
