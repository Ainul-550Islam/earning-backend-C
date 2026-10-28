"""
urls/search_urls.py — NEWLY CREATED
Routes for search, schema, and resource viewsets.
"""
from django.urls import path
from api.alerts.viewsets.search_views import SearchViewSet, SchemaViewSet, ResourceViewSet

app_name = 'search'

urlpatterns = [
    # ── Search ─────────────────────────────────────────────────────────
    path('',                    SearchViewSet.as_view({'get': 'list'}),              name='search-global'),
    path('rules/',              SearchViewSet.as_view({'get': 'search_rules'}),      name='search-rules'),
    path('logs/',               SearchViewSet.as_view({'get': 'search_logs'}),       name='search-logs'),
    path('notifications/',      SearchViewSet.as_view({'get': 'search_notifications'}), name='search-notifications'),
    path('suggestions/',        SearchViewSet.as_view({'get': 'suggestions'}),       name='search-suggestions'),
    path('analytics/',          SearchViewSet.as_view({'get': 'search_analytics'}),  name='search-analytics'),
    path('facets/',             SearchViewSet.as_view({'get': 'search_facets'}),     name='search-facets'),

    # ── Schema ─────────────────────────────────────────────────────────
    path('schema/',             SchemaViewSet.as_view({'get': 'list'}),              name='schema-list'),
    path('schema/get/',         SchemaViewSet.as_view({'get': 'get_schema'}),        name='schema-get'),
    path('schema/validate/',    SchemaViewSet.as_view({'post': 'validate'}),         name='schema-validate'),
    path('schema/webhooks/',    SchemaViewSet.as_view({'get': 'webhook_schemas'}),   name='schema-webhooks'),
    path('schema/system/',      SchemaViewSet.as_view({'get': 'system_schemas'}),    name='schema-system'),

    # ── Resources (import/export) ───────────────────────────────────────
    path('resources/',          ResourceViewSet.as_view({'get': 'list'}),            name='resource-list'),
    path('resources/export/rules/',   ResourceViewSet.as_view({'get': 'export_rules'}),   name='resource-export-rules'),
    path('resources/export/logs/',    ResourceViewSet.as_view({'get': 'export_logs'}),    name='resource-export-logs'),
    path('resources/import/rules/',   ResourceViewSet.as_view({'post': 'import_rules'}),  name='resource-import-rules'),
    path('resources/info/',           ResourceViewSet.as_view({'get': 'resource_info'}),  name='resource-info'),
]
