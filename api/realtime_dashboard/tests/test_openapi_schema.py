"""
Tests for drf-spectacular OpenAPI schema integration (ADDED v1.4.0).

Covers:
  - The 3 schema endpoints (/schema/, /schema/swagger-ui/, /schema/redoc/)
    are actually reachable, not just present in urls.py.
  - The generated schema itself is valid and free of drf-spectacular
    warnings — the ENUM_NAME_OVERRIDES collision fix and the health_check
    inline_serializer fix (see settings.py / views.py) are both locked in
    here so a future change can't silently reintroduce either warning.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestSchemaEndpointsReachable:
    """The three URLs added to urls.py in v1.4.0 must actually resolve."""

    def test_schema_yaml_reachable(self, api_client):
        response = api_client.get(reverse('schema'))
        assert response.status_code == 200
        assert response['Content-Type'].startswith('application/vnd.oai.openapi')

    def test_swagger_ui_reachable(self, api_client):
        response = api_client.get(reverse('swagger-ui'))
        assert response.status_code == 200
        assert b'swagger-ui' in response.content.lower()

    def test_redoc_reachable(self, api_client):
        response = api_client.get(reverse('redoc'))
        assert response.status_code == 200
        assert b'redoc' in response.content.lower()

    def test_schema_endpoints_do_not_require_authentication(self):
        """
        API docs must be reachable by an unauthenticated client (e.g. a
        developer's browser with no session) — otherwise the "public"
        Swagger UI just 403s for everyone.
        """
        anonymous_client = APIClient()
        assert anonymous_client.get(reverse('schema')).status_code == 200
        assert anonymous_client.get(reverse('swagger-ui')).status_code == 200
        assert anonymous_client.get(reverse('redoc')).status_code == 200


@pytest.mark.django_db
class TestSchemaGeneratesWithoutWarnings:
    """
    drf-spectacular emits Python `warnings` (category: UserWarning, via
    its own logger-to-warnings bridge is NOT used — it prints directly to
    stderr through its own `warn()` helper) whenever it cannot cleanly
    introspect a view/serializer/field. We generate the full schema
    in-process and assert none were raised, which is a much stronger
    signal than "the response was 200" — a schema can render successfully
    over HTTP while still containing auto-hashed enum names or gaps for
    specific operations.
    """

    def test_schema_generation_has_no_errors_or_warnings(self):
        """
        drf-spectacular tracks every warn()/error() call it makes during
        generation in a GeneratorStats singleton (this is what backs the
        "Warnings: N (M unique)" summary printed by `manage.py spectacular
        --fail-on-warn`) — reset it, generate, and assert it's still empty.
        A schema can render 200 over HTTP while still containing gaps for
        specific operations, so this is a stronger signal than the
        reachability tests above.
        """
        from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats
        from drf_spectacular.generators import SchemaGenerator
        from drf_spectacular.validation import validate_schema

        reset_generator_stats()
        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)

        assert not GENERATOR_STATS, (
            f'drf-spectacular reported warnings/errors during schema generation: '
            f'warnings={dict(GENERATOR_STATS._warn_cache)} errors={dict(GENERATOR_STATS._error_cache)}'
        )
        validate_schema(schema)  # raises if the schema itself is not valid OpenAPI 3

    def test_status_enums_have_clean_names_not_auto_hashed(self):
        """
        Locks in the ENUM_NAME_OVERRIDES fix in settings.py. Before that
        fix, drf-spectacular fell back to names like "Status3a5Enum"
        because every model's `status` field collided under the same
        auto-generated base name.
        """
        from drf_spectacular.generators import SchemaGenerator

        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)
        component_names = list(schema.get('components', {}).get('schemas', {}).keys())

        assert 'LifecycleStatusEnum' in component_names
        assert 'MetricStatusEnum' in component_names
        assert 'ConnectionStatusEnum' in component_names
        assert not any(
            name.startswith('Status') and name != 'Status'
            and any(c.isdigit() for c in name)
            for name in component_names
        ), f'Found an auto-hashed enum name, ENUM_NAME_OVERRIDES coverage has drifted: {component_names}'

    def test_every_operation_has_a_tag_and_summary(self):
        """
        Locks in the @extend_schema / @extend_schema_view coverage added
        across all 6 viewsets in v1.4.0 — if a new action is ever added
        without @extend_schema, this fails instead of silently shipping
        an undocumented Swagger UI entry.
        """
        from drf_spectacular.generators import SchemaGenerator

        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)

        missing = []
        for path, methods in schema['paths'].items():
            for method, operation in methods.items():
                if method not in ('get', 'post', 'put', 'patch', 'delete'):
                    continue
                if not operation.get('summary'):
                    missing.append(f'{method.upper()} {path}')
                if not operation.get('tags'):
                    missing.append(f'{method.upper()} {path} (no tags)')

        assert missing == [], f'Operations missing summary/tags: {missing}'
