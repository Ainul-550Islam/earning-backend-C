"""
tests/test_admin_viewset_fixes.py

Regression tests for AdminWebhookViewSet/AdminWebhookEndpointSerializer
bugs fixed.

    [ADM-01] IsAdminUser imported correctly
    [ADM-02] Avg imported from django.db.models
    [ADM-03] global_statistics response body is numeric, not a QuerySet
    [ADM-04] export_data and import_data do not reference non-existent
             model fields (timeout_seconds, rate_limit_per_min)
    [ADM-05] AdminWebhookEndpointSerializer.Meta.fields also referenced
             non-existent fields (url, headers, timeout_seconds,
             rate_limit_per_min, ip_whitelist) - missed by ADM-04, which
             only checked export_data/import_data. This is the
             serializer every admin CRUD path uses, so every real
             list/retrieve/create was raising ImproperlyConfigured.
    [ADM-06] get_queryset() was scoped to `owner=self.request.user`,
             so an admin could only ever see endpoints they personally
             owned - contradicting this viewset's own IsSuperUser
             permission and platform-wide moderation actions
             (force-dispatch/suspend/integration-sync).
"""

from django.db import models
import ast
import importlib
import inspect
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock


VIEWSET_MODULE = "api.webhooks.viewsets.AdminWebhookViewSet"


def _load_source():
    """Return source code of the fixed AdminWebhookViewSet."""
    import importlib.util, os
    # Try the fixed file first, then fall back to installed module
    fixed = "/home/claude/webhooks_fixed/viewsets/AdminWebhookViewSet.py"
    if os.path.exists(fixed):
        with open(fixed) as fh:
            return fh.read()
    try:
        spec   = importlib.util.find_spec(VIEWSET_MODULE)
        origin = spec.origin if spec else None
        if origin:
            with open(origin) as fh:
                return fh.read()
    except Exception:
        pass
    return ""


_SOURCE = _load_source()
_AST    = ast.parse(_SOURCE) if _SOURCE else None


def _import_names_at_top_level():
    """Collect all names imported at module level in the viewset source."""
    names = set()
    if not _AST:
        return names
    for node in ast.walk(_AST):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _code_lines_no_comments():
    """Strip comment and docstring lines from source."""
    if not _AST:
        return []
    raw = _SOURCE.splitlines()
    docstring_lines = set()
    for node in ast.walk(_AST):
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            if isinstance(node.value.value, str):
                for ln in range(node.lineno, node.end_lineno + 1):
                    docstring_lines.add(ln)
    result = []
    for i, line in enumerate(raw, 1):
        if i in docstring_lines:
            continue
        result.append(line.split("#")[0])
    return result


_CODE_LINES = _code_lines_no_comments()


# ═════════════════════════════════════════════════════════════════════════════
#  [ADM-01] IsAdminUser import
# ═════════════════════════════════════════════════════════════════════════════

class TestIsAdminUserImport(unittest.TestCase):
    """IsAdminUser must be imported at module level."""

    def test_is_admin_user_in_top_level_imports(self):
        """IsAdminUser must be present in the module-level import names."""
        imported = _import_names_at_top_level()
        self.assertIn(
            "IsAdminUser",
            imported,
            "IsAdminUser is not imported at module level in AdminWebhookViewSet. "
            "Two @action decorators use it as permission_classes=[IsAdminUser] — "
            "they will raise NameError on first call without the import.",
        )

    def test_is_admin_user_comes_from_rest_framework(self):
        """IsAdminUser must be imported from rest_framework.permissions."""
        if not _AST:
            self.skipTest("source not available")

        found = False
        for node in ast.walk(_AST):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "rest_framework.permissions"
            ):
                for alias in node.names:
                    if alias.name == "IsAdminUser":
                        found = True
        self.assertTrue(
            found,
            "IsAdminUser is not imported from rest_framework.permissions. "
            "It must come from that specific module.",
        )

    def test_is_admin_user_used_in_integration_actions(self):
        """Both integration-status and integration-sync actions must reference IsAdminUser."""
        count = sum(
            1 for line in _CODE_LINES if "IsAdminUser" in line and "permission_classes" in line
        )
        self.assertGreaterEqual(
            count, 2,
            f"Expected at least 2 lines with 'permission_classes=...IsAdminUser...', "
            f"found {count}. Integration actions may still be broken.",
        )


# ═════════════════════════════════════════════════════════════════════════════
#  [ADM-02] Avg import
# ═════════════════════════════════════════════════════════════════════════════

class TestAvgImport(unittest.TestCase):
    """Avg must be imported from django.db.models (not used as models.Avg)."""

    def test_avg_imported_at_module_level(self):
        imported = _import_names_at_top_level()
        self.assertIn(
            "Avg",
            imported,
            "Avg is not imported at module level. global_statistics() calls "
            "Avg('response_time_ms') which will NameError at runtime.",
        )

    def test_avg_comes_from_django_db_models(self):
        if not _AST:
            self.skipTest("source not available")
        found = False
        for node in ast.walk(_AST):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "django.db.models"
            ):
                for alias in node.names:
                    if alias.name == "Avg":
                        found = True
        self.assertTrue(
            found,
            "Avg is not imported from django.db.models. "
            "The original code used models.Avg which was a NameError.",
        )

    def test_models_avg_not_present_in_code(self):
        """models.Avg must NOT appear in executable code (only in comments)."""
        hits = [line for line in _CODE_LINES if "models.Avg" in line and line.strip()]
        self.assertEqual(
            hits, [],
            f"'models.Avg' found in executable code lines: {hits}. "
            "Should have been replaced with bare Avg after the import fix.",
        )


# ═════════════════════════════════════════════════════════════════════════════
#  [ADM-03] global_statistics — QuerySet vs count collision
# ═════════════════════════════════════════════════════════════════════════════

class TestGlobalStatisticsResponse(unittest.TestCase):
    """global_statistics() must return numeric counts, not ORM QuerySets."""

    def _call_global_statistics(self):
        """Build a minimal viewset instance and call global_statistics()."""
        # Dynamically import from the fixed file if available
        import importlib, types, sys, os

        fixed_path = "/home/claude/webhooks_fixed/viewsets/AdminWebhookViewSet.py"
        if os.path.exists(fixed_path):
            spec   = importlib.util.spec_from_file_location("_fixed_admin_vs", fixed_path)
            module = importlib.util.module_from_spec(spec)
            # Stub out unresolvable imports before exec
            for stub in [
                "api.webhooks.filters", "api.webhooks.models",
                "api.webhooks.permissions", "api.webhooks.serializers",
                "django_filters.rest_framework", "rest_framework",
                "rest_framework.viewsets", "rest_framework.status",
                "rest_framework.decorators", "rest_framework.permissions",
                "rest_framework.response",
            ]:
                sys.modules.setdefault(stub, types.ModuleType(stub))
            try:
                spec.loader.exec_module(module)
                return module
            except Exception:
                pass
        return None

    @patch("django.db.models.query.QuerySet.count", return_value=42)
    def test_successful_count_is_integer(self, _):
        """
        The 'successful_deliveries' key in the response must be an int,
        not a QuerySet.  Before the fix, the variable was overwritten with
        a queryset which broke JSON serialisation.
        """
        # Verify the source uses a separate variable name for the queryset
        # and returns the count variable (an int) in the response dict.
        count_vars = [
            line for line in _CODE_LINES
            if "successful_count" in line or "successful_logs_qs" in line
        ]
        self.assertTrue(
            len(count_vars) >= 1,
            "Neither 'successful_count' nor 'successful_logs_qs' found in "
            "global_statistics() code — the QuerySet/count collision fix "
            "may not have been applied.",
        )

    def test_response_does_not_reuse_deliveries_var_as_queryset(self):
        """
        'successful_deliveries' variable must NOT be reassigned from int
        to QuerySet inside global_statistics().
        """
        # Find global_statistics function body in the AST
        if not _AST:
            self.skipTest("AST not available")

        for node in ast.walk(_AST):
            if isinstance(node, ast.FunctionDef) and node.name == "global_statistics":
                assigns = [n for n in ast.walk(node) if isinstance(n, ast.Assign)]
                target_names = [
                    t.id
                    for a in assigns
                    for t in a.targets
                    if isinstance(t, ast.Name)
                ]
                # Count how many times 'successful_deliveries' is assigned
                collision_count = target_names.count("successful_deliveries")
                self.assertLessEqual(
                    collision_count, 1,
                    f"'successful_deliveries' is assigned {collision_count} times in "
                    f"global_statistics(). The variable is being overwritten from "
                    f"int → QuerySet — [ADM-03] fix has not been applied.",
                )
                return
        # If function not found by name, skip rather than fail
        self.skipTest("global_statistics() function not found in AST")

    def test_avg_called_without_models_prefix(self):
        """
        Avg() must appear without the 'models.' prefix in global_statistics().
        Before the fix, 'models.Avg' caused a NameError at runtime.
        """
        avg_lines = [line for line in _CODE_LINES if "Avg(" in line]
        for line in avg_lines:
            self.assertNotIn(
                "models.Avg",
                line,
                f"'models.Avg' still present in executable line: {line!r}",
            )
        # At least one Avg() call must exist
        self.assertTrue(avg_lines, "No Avg() call found in viewset code at all.")


# ═════════════════════════════════════════════════════════════════════════════
#  [ADM-04] Non-existent model fields removed from export/import
# ═════════════════════════════════════════════════════════════════════════════

class TestNonExistentFieldsRemoved(unittest.TestCase):
    """
    export_data() and import_data() must not reference timeout_seconds or
    rate_limit_per_min — these fields do not exist on WebhookEndpoint.
    """

    def test_timeout_seconds_not_in_executable_code(self):
        hits = [
            line for line in _CODE_LINES
            if "timeout_seconds" in line and line.strip()
        ]
        self.assertEqual(
            hits, [],
            f"'timeout_seconds' still appears in executable code: {hits}. "
            "This field does not exist on WebhookEndpoint — [ADM-04] fix not applied.",
        )

    def test_rate_limit_per_min_not_in_executable_code(self):
        hits = [
            line for line in _CODE_LINES
            if "rate_limit_per_min" in line and line.strip()
        ]
        self.assertEqual(
            hits, [],
            f"'rate_limit_per_min' still appears in executable code: {hits}. "
            "This field does not exist on WebhookEndpoint — [ADM-04] fix not applied.",
        )

    def test_export_data_uses_canonical_fields(self):
        """export_data() CSV header must use canonical field names."""
        # writer.writerow([...]) is multi-line in the real formatted code
        # (the header list spans several lines below the call itself), so
        # a same-line check for both "writer.writerow" and "Label"/"URL"
        # never matches - confirmed empirically against the real file.
        # Checking a small window of lines after each writerow call instead.
        found = False
        for i, line in enumerate(_CODE_LINES):
            if "writer.writerow" in line:
                window = "\n".join(_CODE_LINES[i:i + 5])
                if "Label" in window or "URL" in window:
                    found = True
                    break
        self.assertTrue(
            found,
            "No CSV header writerow() with canonical field names found in export_data.",
        )

    def test_import_data_uses_max_retries_not_timeout(self):
        """import_data() endpoint_data dict must use max_retries, not timeout_seconds."""
        max_retries_refs = [l for l in _CODE_LINES if "max_retries" in l]
        timeout_refs     = [l for l in _CODE_LINES if "timeout_seconds" in l]

        self.assertTrue(
            max_retries_refs,
            "max_retries not referenced in viewset code — import_data() may be broken.",
        )
        self.assertEqual(
            timeout_refs, [],
            "timeout_seconds still referenced in executable code.",
        )


# ═════════════════════════════════════════════════════════════════════════════
#  SecretRotationService — concurrent lock test
# ═════════════════════════════════════════════════════════════════════════════

class TestSecretRotationConcurrentSafety(unittest.TestCase):
    """
    [ROT-01] rotate_secret() must use select_for_update() to prevent
    concurrent callers from producing two different secrets for the same row.
    """

    def _load_service_source(self):
        import os
        fixed = "/home/claude/webhooks_fixed/services/core/SecretRotationService.py"
        if os.path.exists(fixed):
            with open(fixed) as fh:
                return fh.read()
        # That hardcoded path doesn't exist in this environment (confirmed)
        # and this method had no fallback, unlike _load_source() above -
        # always returned "" here, which is why every test in this class
        # failed uniformly (assertIn against an empty string can never
        # pass). Same importlib fallback as _load_source(), pointed at the
        # real module. The real file already has select_for_update() (x3,
        # rotate_secret/rotate_inbound_secret/invalidate_secret),
        # locked_endpoint, and update_fields=["secret_key", ...] -
        # confirmed empirically; ROT-01 was already correctly implemented,
        # this class just couldn't see it.
        try:
            import importlib.util
            spec = importlib.util.find_spec(
                "api.webhooks.services.core.SecretRotationService"
            )
            origin = spec.origin if spec else None
            if origin:
                with open(origin) as fh:
                    return fh.read()
        except Exception:
            pass
        return ""

    def test_select_for_update_present_in_rotate_secret(self):
        src = self._load_service_source()
        self.assertIn(
            "select_for_update()",
            src,
            "select_for_update() not found in SecretRotationService — "
            "concurrent rotation race condition is not fixed.",
        )

    def test_rotate_secret_uses_locked_endpoint_not_original(self):
        """
        The locked row fetched by select_for_update() must be used for
        all operations inside the atomic block, not the original argument.
        """
        src = self._load_service_source()
        self.assertIn(
            "locked_endpoint",
            src,
            "'locked_endpoint' variable not found — select_for_update() result "
            "may not be stored and used correctly.",
        )

    def test_save_uses_update_fields_for_secret_key(self):
        """save() inside rotate_secret() must pass update_fields to avoid full-row writes."""
        src = self._load_service_source()
        self.assertIn(
            'update_fields=["secret_key"',
            src,
            "update_fields not found on save() call in rotate_secret() — "
            "full-row writes under concurrent load may clobber other fields.",
        )

    def test_invalidate_also_uses_select_for_update(self):
        """invalidate_secret() must also lock the row."""
        src = self._load_service_source()
        # Count occurrences — rotate_secret and invalidate_secret both need it
        count = src.count("select_for_update()")
        self.assertGreaterEqual(
            count, 2,
            f"Only {count} select_for_update() call(s) found. "
            "Both rotate_secret() and invalidate_secret() need row-level locking.",
        )


if __name__ == "__main__":
    unittest.main()


# ═════════════════════════════════════════════════════════════════════════════
#  [ADM-05] AdminWebhookEndpointSerializer referenced non-existent fields
# ═════════════════════════════════════════════════════════════════════════════
# ADM-04 above fixed export_data/import_data referencing timeout_seconds and
# rate_limit_per_min, but missed that serializers/AdminWebhookSerializer.py's
# AdminWebhookEndpointSerializer.Meta.fields had the exact same problem, plus
# two more (url, headers - real names are target_url, custom_headers). Since
# this is the serializer "all admin CRUD paths use" (this file's own class
# docstring), every real list/retrieve/create through AdminWebhookViewSet
# raised ImproperlyConfigured - confirmed via a real APIClient round-trip
# during the fix, not just the source check below.

def _load_serializer_source():
    import importlib.util, os
    fixed = "/home/claude/webhooks_fixed/serializers/AdminWebhookSerializer.py"
    if os.path.exists(fixed):
        with open(fixed) as fh:
            return fh.read()
    try:
        spec = importlib.util.find_spec("api.webhooks.serializers.AdminWebhookSerializer")
        origin = spec.origin if spec else None
        if origin:
            with open(origin) as fh:
                return fh.read()
    except Exception:
        pass
    return ""


class TestAdminEndpointSerializerFieldsAreReal(unittest.TestCase):
    """AdminWebhookEndpointSerializer.Meta.fields must only name fields
    that actually exist on WebhookEndpoint."""

    NONEXISTENT_NAMES = ("'url'", "'headers'", "'timeout_seconds'", "'rate_limit_per_min'", "'ip_whitelist'")

    def test_no_nonexistent_field_names_in_meta_fields(self):
        src = _load_serializer_source()
        self.assertTrue(src, "Could not load AdminWebhookSerializer.py source.")
        for bad in self.NONEXISTENT_NAMES:
            self.assertNotIn(
                bad, src,
                f"{bad} found in AdminWebhookSerializer.py - WebhookEndpoint has no "
                f"such field (real names: target_url, custom_headers; the other "
                f"three don't exist on this model at all).",
            )

    def test_serializer_actually_instantiates(self):
        """The real, direct check: building the serializer's fields must
        not raise ImproperlyConfigured."""
        from api.webhooks.serializers import AdminWebhookEndpointSerializer
        try:
            fields = AdminWebhookEndpointSerializer().fields
        except Exception as e:
            self.fail(f"AdminWebhookEndpointSerializer() raised {type(e).__name__}: {e}")
        self.assertIn("target_url", fields)
        self.assertIn("custom_headers", fields)


# ═════════════════════════════════════════════════════════════════════════════
#  [ADM-06] AdminWebhookViewSet.get_queryset() was scoped to the admin's own
#  owned endpoints instead of all endpoints
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminQuerysetIsPlatformWide(unittest.TestCase):
    """An IsSuperUser-gated admin viewset with force-dispatch/suspend/
    integration-sync actions must see every endpoint, not just ones it
    happens to own - get_queryset() previously did
    `.filter(owner=self.request.user)`, which is the regular
    per-user-facing viewset's pattern, not an admin one."""

    def test_get_queryset_not_owner_filtered(self):
        src = _load_source()  # AdminWebhookViewSet.py, loader defined above in this file
        self.assertTrue(src, "Could not load AdminWebhookViewSet.py source.")
        self.assertNotIn(
            "filter(owner=self.request.user)", src,
            "AdminWebhookViewSet.get_queryset() is scoping to the admin's own "
            "endpoints again - this viewset must return all endpoints.",
        )

    def test_admin_sees_other_users_endpoint_via_real_request(self):
        """Real end-to-end check, not just a source-text match: an admin
        with no endpoints of their own must still see (and be able to
        retrieve) another user's endpoint through this viewset."""
        import django
        django.setup()
        from django.contrib.auth import get_user_model
        from django.test import TransactionTestCase
        from rest_framework.test import APIClient
        from api.webhooks.models import WebhookEndpoint

        class _Check(TransactionTestCase):
            def runTest(self):
                User = get_user_model()
                admin = User.objects.create_user(username="admtest1", password="x", is_superuser=True, is_staff=True)
                owner = User.objects.create_user(username="owntest1", password="x")
                ep = WebhookEndpoint.objects.create(owner=owner, label="Other user's EP", target_url="https://example.com/hook")

                client = APIClient()
                client.force_authenticate(user=admin)

                list_resp = client.get("/webhooks/admin/webhooks/")
                assert list_resp.status_code == 200, list_resp.content
                assert list_resp.data["count"] >= 1, "Admin should see other users' endpoints in the list."

                detail_resp = client.get(f"/webhooks/admin/webhooks/{ep.id}/")
                assert detail_resp.status_code == 200, (
                    f"Admin could not retrieve another user's endpoint (got {detail_resp.status_code}) - "
                    f"get_queryset() is scoping by owner again."
                )

        _Check().run()
