# publisher_tools/mixins.py
"""
DRY Mixins — publisher_tools app।

এই ফাইলটি সব repeated patterns একটি জায়গায় রাখে।

পুরনো pattern (31 files × বারবার):
──────────────────────────────────────────
    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except AttributeError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No publisher profile.')

    @action(...)
    def my_endpoint(self, request):
        publisher = self._get_publisher()
        try:
            from .subfolder.module import SomeClass
            result = SomeClass.objects.filter(publisher=publisher).first()
            ...
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

নতুন pattern (এই মিক্সিন ব্যবহার করে):
──────────────────────────────────────────
    class MyViewSet(PublisherMixin, BaseViewSet):
        @action(...)
        def my_endpoint(self, request):
            publisher = self.publisher
            with self.handle_errors():
                from .subfolder.module import SomeClass
                result = SomeClass.objects.filter(publisher=publisher).first()
                ...
                return self.ok({'data': result})
"""
from contextlib import contextmanager
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status


# ══════════════════════════════════════════════════════════════════════════════
# 1. PublisherMixin
#    Eliminates: 31 × _get_publisher() + 179 × publisher = self._get_publisher()
# ══════════════════════════════════════════════════════════════════════════════

class PublisherMixin:
    """
    Use in any ViewSet that needs publisher access।

    Before (each of 31 view files had this):
        def _get_publisher(self):
            try:
                return self.request.user.publisher_profile
            except AttributeError:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('No publisher profile.')

    After (one definition here, all files inherit):
        class MyViewSet(PublisherMixin, BaseViewSet):
            pass  # self.publisher  বা  self._get_publisher()  both work
    """

    @property
    def publisher(self):
        """
        Cached publisher property।
        self.publisher  →  publisher object (or PermissionDenied)
        """
        if not hasattr(self, '_publisher_cache'):
            self._publisher_cache = self._get_publisher()
        return self._publisher_cache

    def _get_publisher(self):
        """Backward-compatible method (পুরনো code ভাঙবে না)।"""
        try:
            return self.request.user.publisher_profile
        except AttributeError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No publisher profile found.')


# ══════════════════════════════════════════════════════════════════════════════
# 2. ErrorHandlingMixin
#    Eliminates: 372 × try/except (ImportError, Exception) + error_response(503)
# ══════════════════════════════════════════════════════════════════════════════

class ErrorHandlingMixin:
    """
    Use contextmanager to collapse 372 repeated try/except blocks।

    Before (372 times across all views):
        try:
            from .publisher_management.publisher_kyc import PublisherKYC
            kyc = PublisherKYC.objects.filter(publisher=publisher).first()
            return self.success_response(data={...})
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    After (one pattern):
        with self.handle_errors() as err:
            from .publisher_management.publisher_kyc import PublisherKYC
            kyc = PublisherKYC.objects.filter(publisher=publisher).first()
            return self.ok({'kyc_id': kyc.pk})
        return err.response  # only reached if exception occurred
    """

    @contextmanager
    def handle_errors(self, status_code: int = 503):
        """
        Context manager: catches all errors, returns error response।
        Usage:
            with self.handle_errors() as guard:
                ...your logic...
                return self.ok({'result': data})
            return guard.response
        """
        guard = _ErrorGuard()
        try:
            yield guard
        except (ImportError, AttributeError) as e:
            guard.response = self._build_error(
                f'Module not available: {e}', 503
            )
        except Exception as e:
            guard.response = self._build_error(str(e), status_code)

    def _build_error(self, message: str, status_code: int) -> Response:
        """Build a standardised error response।"""
        # Delegates to BaseViewSet.error_response if available
        if hasattr(self, 'error_response'):
            return self.error_response(message, status_code=status_code)
        return Response(
            {'success': False, 'error': message},
            status=status_code,
        )

    def ok(self, data=None, message: str = '', status_code: int = 200) -> Response:
        """
        Shorthand for success_response।
        Replaces: return self.success_response(data=..., message=...)
        """
        if hasattr(self, 'success_response'):
            return self.success_response(data=data or {}, message=message)
        return Response(
            {'success': True, 'data': data or {}, 'message': message},
            status=status_code,
        )

    def run_script(
        self,
        module_path: str,
        fn_name: str,
        *,
        args: tuple = (),
        kwargs: dict = None,
        success_message: str = 'Done.',
        dict_key: str = 'result',
    ) -> Response:
        """
        One-line script runner।
        Replaces 372 identical try/except import blocks in views_scripts*.py:

        Before (repeated 372×):
            try:
                from .scripts.backup_data import backup_publisher_earnings
                result = backup_publisher_earnings(publisher_id=pub_id, days=days)
            except (ImportError, Exception) as e:
                return self.error_response(str(e), status_code=503)
            return self.success_response(
                data=result if isinstance(result, dict) else {'backup': True},
                message='Backup complete.',
            )

        After (one line):
            return self.run_script(
                'scripts.backup_data', 'backup_publisher_earnings',
                kwargs={'publisher_id': pub_id, 'days': days},
                success_message='Backup complete.',
            )
        """
        kwargs = kwargs or {}
        try:
            # Dynamic import from relative module
            parts = module_path.split('.')
            pkg   = __import__(
                f'publisher_tools.{module_path}',
                fromlist=[fn_name],
            )
            fn     = getattr(pkg, fn_name)
            result = fn(*args, **kwargs)
        except ImportError as e:
            return self._build_error(f'Module not available: {e}', 503)
        except Exception as e:
            return self._build_error(str(e), 503)

        data = result if isinstance(result, dict) else {dict_key: True}
        return self.ok(data, message=success_message)


class _ErrorGuard:
    """Internal holder for error response set by handle_errors context manager।"""
    response: Response = None


# ══════════════════════════════════════════════════════════════════════════════
# 3. AdminOnlyMixin
#    Eliminates: 14 × permission_classes = [IsAuthenticated, IsAdminUser]
# ══════════════════════════════════════════════════════════════════════════════

class AdminOnlyMixin:
    """
    Declares admin-only permission once।

    Before (14 view files each had):
        permission_classes = [IsAuthenticated, IsAdminUser]

    After:
        class MyViewSet(AdminOnlyMixin, BaseViewSet):
            pass
    """
    permission_classes = [IsAuthenticated, IsAdminUser]


# ══════════════════════════════════════════════════════════════════════════════
# 4. PublisherOrAdminMixin
#    Standard: IsAuthenticated + (IsPublisher OR IsAdminUser)
# ══════════════════════════════════════════════════════════════════════════════

class PublisherOrAdminMixin:
    """
    Publisher or Admin permission।
    Replaces: from .permissions import IsPublisher, IsAdminOrPublisher
              permission_classes = [IsAuthenticated, IsAdminOrPublisher]
    (repeated in 17 view files)
    """
    @property
    def permission_classes(self):
        try:
            from .permissions import IsAdminOrPublisher
            return [IsAuthenticated, IsAdminOrPublisher]
        except ImportError:
            return [IsAuthenticated]


# ══════════════════════════════════════════════════════════════════════════════
# 5. DateFilterMixin
#    Eliminates repeated start_date/end_date/publisher_id filter logic
# ══════════════════════════════════════════════════════════════════════════════

class DateFilterMixin:
    """
    Common queryset filters for date range, publisher, processed status।

    Replaces repeated filter logic across WarehouseBaseViewSet methods
    and views_analytics*.py files।
    """

    def apply_publisher_filter(self, qs):
        """?publisher_id=PUB123 filter।"""
        pub_id = self.request.query_params.get('publisher_id')
        if pub_id:
            qs = qs.filter(publisher__publisher_id=pub_id)
        return qs

    def apply_date_filter(self, qs, field: str = 'record_date'):
        """?start_date=2025-01-01&end_date=2025-01-31 filter।"""
        start = self.request.query_params.get('start_date')
        end   = self.request.query_params.get('end_date')
        if start:
            qs = qs.filter(**{f'{field}__gte': start})
        if end:
            qs = qs.filter(**{f'{field}__lte': end})
        return qs

    def apply_processed_filter(self, qs):
        """?is_processed=true|false filter।"""
        val = self.request.query_params.get('is_processed')
        if val is not None:
            qs = qs.filter(is_processed=val.lower() == 'true')
        return qs

    def apply_standard_filters(self, qs, date_field: str = 'record_date'):
        """
        Apply all three filters at once।
        Replaces 3-line filter chain repeated in every warehouse ViewSet:
            qs = self._publisher_filter(qs)
            qs = self._date_filter(qs)
            qs = self._processed_filter(qs)
        """
        return self.apply_processed_filter(
            self.apply_date_filter(
                self.apply_publisher_filter(qs),
                field=date_field,
            )
        )


# ══════════════════════════════════════════════════════════════════════════════
# 6. SubfolderMixin
#    Safe import helper for publisher_management, app_management, etc.
# ══════════════════════════════════════════════════════════════════════════════

class SubfolderMixin:
    """
    Safe model lookup from publisher_management/app_management subfolders।
    Eliminates repeated try/except import + filter pattern।

    Before (repeated 50+ times across views):
        try:
            from .publisher_management.publisher_kyc import PublisherKYC
            obj = PublisherKYC.objects.filter(publisher=publisher).first()
            if not obj:
                return self.success_response(data={'kyc': None, 'message': '...'})
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    After:
        obj = self.get_subfolder_object(
            'publisher_management.publisher_kyc', 'PublisherKYC',
            publisher=publisher,
        )
        if obj is None:
            return self.ok({'kyc': None, 'message': 'Not found.'})
    """

    def get_subfolder_model(self, dotted_path: str, class_name: str):
        """
        Import a model class from a subfolder।
        Returns class or None (never raises)।

        dotted_path: 'publisher_management.publisher_kyc'
        class_name:  'PublisherKYC'
        """
        try:
            module = __import__(
                f'publisher_tools.{dotted_path}',
                fromlist=[class_name],
            )
            return getattr(module, class_name, None)
        except (ImportError, AttributeError):
            return None

    def get_subfolder_object(
        self,
        dotted_path: str,
        class_name: str,
        **filter_kwargs,
    ):
        """
        Import model class + run filter().first() in one call।
        Returns model instance or None (never raises)।
        """
        model = self.get_subfolder_model(dotted_path, class_name)
        if model is None:
            return None
        try:
            return model.objects.filter(**filter_kwargs).first()
        except Exception:
            return None

    def get_subfolder_queryset(
        self,
        dotted_path: str,
        class_name: str,
        **filter_kwargs,
    ):
        """Same as above but returns queryset (not first())。"""
        model = self.get_subfolder_model(dotted_path, class_name)
        if model is None:
            return None
        try:
            return model.objects.filter(**filter_kwargs)
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# 7. Convenience combined mixin
# ══════════════════════════════════════════════════════════════════════════════

class PublisherViewMixin(PublisherMixin, ErrorHandlingMixin, SubfolderMixin):
    """
    All-in-one mixin for publisher-facing ViewSets।
    Inherit this instead of defining _get_publisher() + handle_errors() separately।

    Usage:
        class PublisherAdvancedViewSet(PublisherViewMixin, BaseViewSet):
            permission_classes = [IsAuthenticated, IsPublisher]
    """
    pass


class AdminScriptViewMixin(AdminOnlyMixin, ErrorHandlingMixin):
    """
    All-in-one mixin for admin script runner ViewSets。
    Replaces AdminOnlyMixin + identical try/except blocks।

    Usage:
        class ScriptRunnerViewSet(AdminScriptViewMixin, BaseViewSet):
            pass
    """
    pass


class WarehouseViewMixin(AdminOnlyMixin, DateFilterMixin):
    """
    Mixin for analytics warehouse ViewSets।
    Provides: admin-only permission + standard date/publisher/processed filters।
    """

    def apply_filters(self, qs, date_field: str = 'record_date'):
        """Single call replaces 3-method chain in every warehouse ViewSet。"""
        return self.apply_standard_filters(qs, date_field=date_field)
