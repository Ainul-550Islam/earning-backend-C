# kyc/openapi/schema.py  ── WORLD #1
"""
OpenAPI 3.0 / Swagger schema for the KYC system.
Accessible at: GET /api/kyc/docs/     (Swagger UI)
               GET /api/kyc/redoc/    (ReDoc)
               GET /api/kyc/schema/   (Raw JSON/YAML)

Usage in settings.py:
    INSTALLED_APPS += ['drf_spectacular']

Usage in urls.py:
    from kyc.openapi.schema import get_kyc_schema_urls
    urlpatterns += get_kyc_schema_urls()
"""
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter,
    OpenApiExample, OpenApiResponse,
)
from drf_spectacular.openapi import AutoSchema
import logging

logger = logging.getLogger(__name__)


# ── Reusable schema decorators ────────────────────────────

kyc_status_schema = extend_schema(
    summary="Get KYC submission status",
    description="""
Returns the current user's latest KYC submission status.
If no submission exists, returns `status: not_submitted`.

**Authentication**: Bearer token required.
    """,
    responses={
        200: OpenApiResponse(description="KYC status object"),
        401: OpenApiResponse(description="Unauthorized"),
    },
    tags=["KYC — User"],
)

kyc_submit_schema = extend_schema(
    summary="Submit KYC documents",
    description="""
Submit KYC documents for verification.

**Multipart form data required:**
- `document_type`: `nid` | `passport` | `driving_license`
- `document_number`: NID/Passport number
- `nid_front`: Front image of ID document (JPEG/PNG, max 5MB)
- `nid_back`: Back image of ID document (JPEG/PNG, max 5MB)
- `selfie_with_note`: Selfie holding handwritten note (JPEG/PNG, max 5MB)

**Notes:**
- Minimum image resolution: 400×300 pixels
- Verified KYC cannot be re-submitted
    """,
    tags=["KYC — User"],
)

kyc_fraud_check_schema = extend_schema(
    summary="Run fraud/audit check",
    description="""
Triggers automated fraud scoring on uploaded documents.
Computes: image clarity score, document matching score, face liveness.
Moves progress from 10% → 60-75%.
    """,
    tags=["KYC — User"],
)

aml_screen_schema = extend_schema(
    summary="Run AML/PEP/Sanctions screening",
    description="""
Screens KYC subject against:
- UN Consolidated Sanctions List
- OFAC SDN List (US Treasury)
- EU Financial Sanctions
- Bangladesh BFIU Watchlist
- PEP (Politically Exposed Persons) database

**Providers**: `mock` | `complyadvantage` | `refinitiv`
    """,
    tags=["AML — Admin"],
    parameters=[
        OpenApiParameter(name="kyc_id", location="path", description="KYC record ID"),
    ],
)

kyb_submit_schema = extend_schema(
    summary="Submit business (KYB) verification",
    description="""
Submit Know Your Business (KYB) verification.
Supports: Sole Proprietorship, Partnership, Private Limited, Public Limited, NGO.

**Required documents:**
- Trade license
- TIN certificate
- Memorandum of Association (for companies)
- Director/UBO ID documents
    """,
    tags=["KYB — Business Verification"],
)

gdpr_erasure_schema = extend_schema(
    summary="Request GDPR data erasure",
    description="""
GDPR Article 17 — Right to Erasure.
Anonymizes all PII from KYC records.
Audit trail is retained (legal obligation under FATF Rec. 11).
Response within 30 days as per GDPR requirement.
    """,
    tags=["GDPR — Compliance"],
)


# ── OpenAPI settings for drf-spectacular ─────────────────

SPECTACULAR_SETTINGS = {
    'TITLE': 'KYC System API — World #1',
    'DESCRIPTION': """
## Bangladesh's Enterprise KYC/AML Platform

### Features
- NID, Passport, Driving License verification
- Face matching + Liveness detection + Deepfake protection
- AML/PEP/Sanctions screening (UN, OFAC, EU, BD BFIU)
- GDPR / Bangladesh PDPA 2023 compliant
- KYB (Know Your Business) + UBO disclosure
- Transaction monitoring + SAR filing
- Multi-tenant SaaS architecture
- Real-time risk scoring + fraud detection

### Authentication
All endpoints require Bearer token authentication:
```
Authorization: Bearer <your-jwt-token>
```

### Rate Limits
- KYC submit: 5 requests/hour per user
- Fraud check: 10 requests/hour per user
- Admin endpoints: 1000 requests/hour

### Status Codes
- `200` Success
- `201` Created
- `400` Validation error
- `401` Unauthenticated
- `403` Forbidden / Blacklisted
- `404` Not found
- `409` Conflict (duplicate)
- `422` Unprocessable (OCR/image error)
- `429` Rate limited
- `503` External service unavailable
    """,
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
    'TAGS': [
        {'name': 'KYC — User',         'description': 'User-facing KYC endpoints'},
        {'name': 'KYC — Admin',         'description': 'Admin KYC management endpoints'},
        {'name': 'AML — Admin',         'description': 'AML/PEP/Sanctions screening'},
        {'name': 'KYB — Business Verification', 'description': 'Know Your Business (KYB)'},
        {'name': 'Liveness',            'description': 'Liveness + deepfake detection'},
        {'name': 'GDPR — Compliance',   'description': 'GDPR + consent management'},
        {'name': 'Transaction Monitoring', 'description': 'AML transaction monitoring rules'},
        {'name': 'Analytics',           'description': 'Dashboard analytics + reports'},
        {'name': 'Security',            'description': 'Blacklist + IP + fraud management'},
        {'name': 'Webhooks',            'description': 'Webhook endpoint management'},
        {'name': 'System',              'description': 'Health check + feature flags'},
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'filter': True,
    },
    'REDOC_UI_SETTINGS': {
        'hideDownloadButton': False,
    },
    'POSTPROCESSING_HOOKS': [],
    'ENUM_GENERATE_CHOICE_DESCRIPTION': True,
    'SERVERS': [
        {'url': 'https://api.yourdomain.com', 'description': 'Production'},
        {'url': 'https://sandbox.yourdomain.com', 'description': 'Sandbox'},
        {'url': 'http://localhost:8000', 'description': 'Local development'},
    ],
}


def get_kyc_schema_urls():
    """
    Add to your main urls.py:
        from kyc.openapi.schema import get_kyc_schema_urls
        urlpatterns += get_kyc_schema_urls()
    """
    try:
        from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
        from django.urls import path
        return [
            path('api/kyc/schema/',  SpectacularAPIView.as_view(),    name='kyc-schema'),
            path('api/kyc/docs/',    SpectacularSwaggerView.as_view(url_name='kyc-schema'), name='kyc-swagger-ui'),
            path('api/kyc/redoc/',   SpectacularRedocView.as_view(url_name='kyc-schema'),   name='kyc-redoc'),
        ]
    except ImportError:
        logger.warning("drf-spectacular not installed. Run: pip install drf-spectacular")
        return []
