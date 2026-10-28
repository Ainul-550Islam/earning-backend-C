# =============================================================================
# api/auto_mod/openapi.py
# =============================================================================
"""
OpenAPI / Swagger documentation configuration for auto_mod.

Setup:
    pip install drf-spectacular

    In settings.py add:
        INSTALLED_APPS += ['drf_spectacular']
        REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'

    In your root urls.py:
        from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
        urlpatterns += [
            path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
            path('api/docs/',   SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        ]
"""
from __future__ import annotations

# Graceful degradation — drf_spectacular is optional
try:
    from drf_spectacular.utils import (
        extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
    )
    from drf_spectacular.types import OpenApiTypes
    SPECTACULAR_AVAILABLE = True
except ImportError:
    SPECTACULAR_AVAILABLE = False

    # No-op decorators when drf_spectacular is not installed
    def extend_schema(*args, **kwargs):
        def decorator(fn): return fn
        return decorator

    def extend_schema_view(**kwargs):
        def decorator(cls): return cls
        return decorator

    class OpenApiParameter:
        QUERY = "query"
        PATH  = "path"
        def __init__(self, *a, **kw): pass

    class OpenApiTypes:
        STR = str; INT = int; FLOAT = float; BOOL = bool; UUID = str


# =============================================================================
# Schema decorators for auto_mod ViewSets
# =============================================================================

SUBMISSION_LIST_SCHEMA = extend_schema(
    summary="List suspicious submissions",
    description=(
        "Returns paginated list of SuspiciousSubmissions filtered by status, "
        "submission_type, risk_level, and date range. "
        "Supports ordering by created_at, risk_score, ai_confidence."
    ),
    parameters=[
        OpenApiParameter("status",          OpenApiTypes.STR,  description="Filter by status"),
        OpenApiParameter("submission_type", OpenApiTypes.STR,  description="Filter by type"),
        OpenApiParameter("risk_level",      OpenApiTypes.STR,  description="low|medium|high"),
        OpenApiParameter("created_after",   OpenApiTypes.STR,  description="ISO datetime"),
        OpenApiParameter("created_before",  OpenApiTypes.STR,  description="ISO datetime"),
        OpenApiParameter("ordering",        OpenApiTypes.STR,  description="-created_at,-risk_score"),
    ],
    tags=["Moderation — Submissions"],
)

SUBMISSION_DETAIL_SCHEMA = extend_schema(
    summary="Retrieve a submission",
    tags=["Moderation — Submissions"],
)

SUBMISSION_APPROVE_SCHEMA = extend_schema(
    summary="Human-approve a submission",
    description="Mark a submission as HUMAN_APPROVED. Requires moderator permission.",
    tags=["Moderation — Submissions"],
)

SUBMISSION_REJECT_SCHEMA = extend_schema(
    summary="Human-reject a submission",
    tags=["Moderation — Submissions"],
)

APPEAL_CREATE_SCHEMA = extend_schema(
    summary="Submit an appeal for a moderation decision",
    description=(
        "Creates a new ModerationAppeal for the given decision. "
        "Subject to appeal window (30 days) and duplicate checks."
    ),
    tags=["Moderation — Appeals"],
)

APPEAL_RESOLVE_SCHEMA = extend_schema(
    summary="Resolve an appeal",
    tags=["Moderation — Appeals"],
)

BOT_START_SCHEMA = extend_schema(
    summary="Start a TaskBot",
    tags=["Moderation — Bots"],
)

BOT_STOP_SCHEMA = extend_schema(
    summary="Stop a TaskBot",
    tags=["Moderation — Bots"],
)

ML_DEPLOY_SCHEMA = extend_schema(
    summary="Deploy an ML model version",
    description="Deploy a trained model version to production. Requires accuracy >= 80%.",
    tags=["Moderation — ML Models"],
)

ML_RETIRE_SCHEMA = extend_schema(
    summary="Retire an ML model version",
    tags=["Moderation — ML Models"],
)

DASHBOARD_SCHEMA = extend_schema(
    summary="Real-time moderation dashboard metrics",
    description=(
        "Returns live KPIs: pending count, approved/rejected today, "
        "avg AI confidence, queue depth, bot health, top-risk submissions."
    ),
    tags=["Moderation — Dashboard"],
    responses={200: {
        "type": "object",
        "properties": {
            "submissions": {"type": "object"},
            "queue":       {"type": "object"},
            "bots":        {"type": "object"},
            "top_risk_submissions": {"type": "array"},
        }
    }},
)

QUEUE_ASSIGN_SCHEMA = extend_schema(
    summary="Assign queue item to a moderator",
    tags=["Moderation — Queue"],
)

QUEUE_ESCALATE_SCHEMA = extend_schema(
    summary="Escalate a queue item",
    tags=["Moderation — Queue"],
)

COMPLIANCE_REPORT_SCHEMA = extend_schema(
    summary="Generate compliance report",
    description="Generate GDPR/CCPA/HIPAA compliance report for the moderation module.",
    tags=["Moderation — Compliance"],
)


# =============================================================================
# SPECTACULAR_SETTINGS to add to Django settings.py
# =============================================================================

SPECTACULAR_SETTINGS = {
    "TITLE":          "auto_mod API",
    "DESCRIPTION":    "CPAlead-grade auto-moderation system — task proof verification, fraud detection, compliance.",
    "VERSION":        "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Moderation — Submissions", "description": "Proof submission CRUD and decisions"},
        {"name": "Moderation — Appeals",     "description": "Appeal creation, assignment, resolution"},
        {"name": "Moderation — Bots",        "description": "TaskBot lifecycle management"},
        {"name": "Moderation — Queue",       "description": "Moderation queue assignment and escalation"},
        {"name": "Moderation — ML Models",   "description": "ML model version management"},
        {"name": "Moderation — Compliance",  "description": "GDPR/CCPA compliance and audit reports"},
        {"name": "Moderation — Dashboard",   "description": "Real-time metrics and KPIs"},
    ],
}
