# viewsets/__init__.py
# All viewsets from original views.py are here + new ones
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser, AllowAny, IsAuthenticated
from rest_framework.decorators import action, api_view, permission_classes
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)


class LanguageViewSet(viewsets.ModelViewSet):
    """Language ViewSet — আগের সব logic রাখা হয়েছে"""
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'code'

    def get_queryset(self):
        from ..models.core import Language
        if self.request.user.is_staff:
            return Language.objects.all().order_by('-is_default', 'name')
        return Language.objects.filter(is_active=True).order_by('-is_default', 'name')

    def get_serializer_class(self):
        from ..serializers.language import LanguageSerializer
        return LanguageSerializer

    @action(detail=False, methods=['get'])
    def default(self, request):
        from ..models.core import Language
        try:
            lang = Language.objects.filter(is_default=True, is_active=True).first()
            if not lang:
                lang = Language.objects.filter(is_active=True).first()
            if lang:
                return Response(self.get_serializer(lang).data)
            return Response({'error': 'No active language found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def set_default(self, request, code=None):
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        language = self.get_object()
        language.is_default = True
        language.save()
        return Response({'message': f'{language.name} is now default.'})

    @action(detail=True, methods=['get'])
    def coverage(self, request, code=None):
        from ..models.core import TranslationKey, Translation
        language = self.get_object()
        total = TranslationKey.objects.count()
        translated = Translation.objects.filter(language=language, is_approved=True).count()
        return Response({'language': code, 'total_keys': total, 'translated': translated,
                         'coverage_percent': round(translated/total*100, 2) if total > 0 else 0})


class TranslationViewSet(viewsets.ModelViewSet):
    """Translation ViewSet — আগের সব logic রাখা হয়েছে"""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from ..models.core import Translation
        qs = Translation.objects.all()
        lang_code = self.request.query_params.get('language')
        if lang_code:
            qs = qs.filter(language__code=lang_code)
        if not self.request.user.is_staff:
            qs = qs.filter(is_approved=True)
        return qs.select_related('key', 'language')

    def get_serializer_class(self):
        from ..serializers.translation import TranslationSerializer
        return TranslationSerializer

    @action(detail=False, methods=['post'])
    def export(self, request):
        from ..services.translation.TranslationExportService import TranslationExportService
        lang_code = request.data.get('language', 'en')
        fmt = request.data.get('format', 'json')
        service = TranslationExportService()
        result = service.export_json(lang_code)
        return Response({'language': lang_code, 'translations': result.get('data', {}), 'count': result.get('count', 0)})

    @action(detail=False, methods=['post'])
    def import_translations(self, request):
        from ..services.translation.TranslationImportService import TranslationImportService
        lang_code = request.data.get('language', 'en')
        data = request.data.get('translations', {})
        service = TranslationImportService()
        result = service.import_json(data, lang_code)
        return Response(result)

    @action(detail=False, methods=['get'])
    def by_language(self, request):
        from ..models.core import Translation
        lang_code = request.query_params.get('code')
        if not lang_code:
            return Response({'error': 'Language code required'}, status=status.HTTP_400_BAD_REQUEST)
        translations = Translation.objects.filter(language__code=lang_code, is_approved=True).select_related('key')
        return Response({'language': lang_code, 'translations': {t.key.key: t.value for t in translations}})

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response({'error': 'Expected a list'}, status=status.HTTP_400_BAD_REQUEST)
        created, errors = [], []
        for item in data:
            serializer = self.get_serializer(data=item)
            if serializer.is_valid():
                serializer.save()
                created.append(serializer.data)
            else:
                errors.append({'data': item, 'errors': serializer.errors})
        return Response({'created': created, 'errors': errors, 'total': len(created)},
                        status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)


class TranslationKeyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'key'

    def get_queryset(self):
        from ..models.core import TranslationKey
        qs = TranslationKey.objects.all()
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        namespace = self.request.query_params.get('namespace')
        if namespace:
            qs = qs.filter(namespace=namespace)
        return qs

    def get_serializer_class(self):
        from ..serializers.translation import TranslationKeySerializer
        return TranslationKeySerializer

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        from ..models.core import TranslationKey
        categories = TranslationKey.objects.values_list('category', flat=True).distinct()
        result = {}
        for cat in categories:
            if cat:
                result[cat] = list(TranslationKey.objects.filter(category=cat).values('key', 'description', 'namespace'))
        return Response(result)


class MissingTranslationViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['language', 'resolved']
    search_fields = ['key']
    ordering_fields = ['created_at', 'occurrence_count']

    def get_queryset(self):
        from ..models.translation import MissingTranslation
        return MissingTranslation.objects.all()

    def get_serializer_class(self):
        from ..serializers.missing_translation import MissingTranslationSerializer
        return MissingTranslationSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [AllowAny()]


class TranslationCacheViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from ..models.translation import TranslationCache
        return TranslationCache.objects.filter(expires_at__gt=timezone.now())

    def get_serializer_class(self):
        from ..serializers.cache import TranslationCacheSerializer
        return TranslationCacheSerializer

    @action(detail=False, methods=['post'], url_path='clean-expired')
    def clean_expired(self, request):
        from ..models.translation import TranslationCache
        deleted_count, _ = TranslationCache.clean_expired()
        return Response({'message': f'Deleted {deleted_count} expired cache entries.', 'status': 'success'})

    @action(detail=False, methods=['get'], url_path='stats')
    def cache_stats(self, request):
        from ..models.translation import TranslationCache
        total = TranslationCache.objects.count()
        active = TranslationCache.objects.filter(expires_at__gt=timezone.now()).count()
        return Response({'total_entries': total, 'active_entries': active, 'expired_entries': total - active})


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['continent', 'is_active', 'is_eu_member']
    search_fields = ['name', 'code', 'native_name']

    def get_queryset(self):
        from ..models.core import Country
        return Country.objects.filter(is_active=True).order_by('name')

    def get_serializer_class(self):
        from ..serializers.country import CountrySerializer
        return CountrySerializer


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    lookup_field = 'code'

    def get_queryset(self):
        from ..models.core import Currency
        return Currency.objects.filter(is_active=True).order_by('code')

    def get_serializer_class(self):
        from ..serializers.currency import CurrencySerializer
        return CurrencySerializer

    @action(detail=False, methods=['get'])
    def convert(self, request):
        from decimal import Decimal, InvalidOperation
        from ..services.currency.CurrencyConversionService import CurrencyConversionService
        try:
            amount = Decimal(request.query_params.get('amount', '1'))
            from_code = request.query_params.get('from', 'USD').upper()
            to_code = request.query_params.get('to', 'BDT').upper()
            service = CurrencyConversionService()
            result = service.convert_and_log(amount, from_code, to_code)
            return Response(result)
        except (InvalidOperation, Exception) as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TimezoneViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]

    def get_queryset(self):
        from ..models.core import Timezone
        return Timezone.objects.filter(is_active=True).order_by('offset_seconds', 'name')

    def get_serializer_class(self):
        from ..serializers.timezone import TimezoneSerializer
        return TimezoneSerializer


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['country', 'is_capital', 'is_active']
    search_fields = ['name', 'native_name', 'iata_code']

    def get_queryset(self):
        from ..models.core import City
        return City.objects.filter(is_active=True).select_related('country', 'timezone').order_by('country__name', 'name')

    def get_serializer_class(self):
        from ..serializers.city import CitySerializer
        return CitySerializer

    @action(detail=False, methods=['get'])
    def search(self, request):
        from ..services.geo.CityService import CityService
        query = request.query_params.get('q', '')
        country_code = request.query_params.get('country', '')
        if not query:
            return Response({'error': 'q parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        service = CityService()
        results = service.autocomplete(query, country_code)
        return Response({'results': results, 'count': len(results)})


class ExchangeRateViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['from_currency', 'to_currency', 'source']

    def get_queryset(self):
        from ..models.currency import ExchangeRate
        return ExchangeRate.objects.order_by('-date', '-created_at')

    def get_serializer_class(self):
        from ..serializers.currency import CurrencyExchangeRateSerializer
        return CurrencyExchangeRateSerializer


class TranslationMemoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['source_language', 'target_language', 'domain', 'is_approved']
    search_fields = ['source_text', 'target_text', 'domain']

    def get_queryset(self):
        from ..models.translation import TranslationMemory
        return TranslationMemory.objects.select_related('source_language', 'target_language').order_by('-usage_count')

    def get_serializer_class(self):
        from ..serializers.translation_memory import TranslationMemorySerializer
        return TranslationMemorySerializer

    @action(detail=False, methods=['post'])
    def search(self, request):
        from ..services.translation.TranslationMemoryService import TranslationMemoryService
        source_text = request.data.get('source_text', '')
        source_lang = request.data.get('source_lang', 'en')
        target_lang = request.data.get('target_lang', 'bn')
        domain = request.data.get('domain', '')
        min_score = float(request.data.get('min_score', 70.0))
        max_results = int(request.data.get('max_results', 5))
        if not source_text:
            return Response({'error': 'source_text required'}, status=status.HTTP_400_BAD_REQUEST)
        service = TranslationMemoryService()
        matches = service.search(source_text, source_lang, target_lang, domain, min_score, max_results)
        return Response({
            'query': source_text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'min_score': min_score,
            'count': len(matches),
            'matches': [
                {
                    'score': round(m['score'], 1),
                    'type': m['type'],
                    'source_text': m['source_text'],
                    'target_text': m['target_text'],
                    'is_approved': m['is_approved'],
                    'quality_rating': m['quality_rating'],
                    'domain': m['domain'],
                    'tm_id': m['entry'].pk,
                }
                for m in matches
            ]
        })

    @action(detail=False, methods=['post'])
    def import_tmx(self, request):
        """TMX file import করে"""
        from ..services.translation.TranslationMemoryService import TranslationMemoryService
        source_lang = request.data.get('source_lang', 'en')
        target_lang = request.data.get('target_lang', 'bn')
        tmx_content = request.data.get('tmx_content', '')
        if not tmx_content:
            return Response({'error': 'tmx_content required'}, status=status.HTTP_400_BAD_REQUEST)
        service = TranslationMemoryService()
        result = service.import_tmx(tmx_content, source_lang, target_lang)
        return Response(result)

    @action(detail=False, methods=['get'])
    def export_tmx(self, request):
        """TM segments TMX format-এ export করে"""
        from ..services.translation.TranslationMemoryService import TranslationMemoryService
        source_lang = request.query_params.get('source_lang', 'en')
        target_lang = request.query_params.get('target_lang', 'bn')
        domain = request.query_params.get('domain', '')
        service = TranslationMemoryService()
        tmx = service.export_tmx(source_lang, target_lang, domain)
        from django.http import HttpResponse
        return HttpResponse(tmx, content_type='application/x-tmx+xml',
                           headers={'Content-Disposition': f'attachment; filename="tm_{source_lang}_{target_lang}.tmx"'})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """TM statistics"""
        from ..services.translation.TranslationMemoryService import TranslationMemoryService
        source_lang = request.query_params.get('source_lang', 'en')
        target_lang = request.query_params.get('target_lang', 'bn')
        return Response(TranslationMemoryService().get_stats(source_lang, target_lang))


class TranslationGlossaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['source_language', 'domain', 'is_do_not_translate', 'is_brand_term']
    search_fields = ['source_term', 'definition']

    def get_queryset(self):
        from ..models.translation import TranslationGlossary
        return TranslationGlossary.objects.select_related('source_language').order_by('source_term')

    def get_serializer_class(self):
        from ..serializers.glossary import GlossaryTermSerializer
        return GlossaryTermSerializer


class TranslationCoverageViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from ..models.analytics import TranslationCoverage
        return TranslationCoverage.objects.select_related('language').order_by('-coverage_percent')

    def get_serializer_class(self):
        from ..serializers.coverage import TranslationCoverageSerializer
        return TranslationCoverageSerializer

    @action(detail=False, methods=['post'])
    def recalculate(self, request):
        if not request.user.is_staff:
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        from ..services.translation.TranslationCoverageService import TranslationCoverageService
        service = TranslationCoverageService()
        results = service.calculate_all()
        return Response({'success': True, 'languages': len(results), 'results': results})


class GeoIPViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def lookup(self, request):
        from ..services.geo.GeoIPService import GeoIPService
        ip_param = request.query_params.get('ip')
        if ip_param:
            ip_address = ip_param.strip()
        else:
            x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR', '')
        service = GeoIPService()
        result = service.lookup(ip_address)
        return Response({'success': True, 'data': result})


class AutoTranslateViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['post'])
    def translate_missing(self, request):
        from ..services.translation.AutoTranslationService import AutoTranslationService
        lang_code = request.data.get('language_code')
        limit = request.data.get('limit', 50)
        dry_run = request.data.get('dry_run', False)
        if not lang_code:
            return Response({'error': 'language_code required'}, status=status.HTTP_400_BAD_REQUEST)
        service = AutoTranslationService()
        result = service.translate_missing(lang_code, limit=int(limit), dry_run=dry_run)
        return Response(result)


class PublicViewSet(viewsets.ViewSet):
    """Unauthenticated translation fetch — for frontend"""
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path='translations/(?P<lang_code>[^/.]+)')
    def get_translations(self, request, lang_code=None):
        from ..models.core import Language, Translation
        from django.core.cache import cache
        cache_key = f"public_translations_{lang_code}"
        cached = cache.get(cache_key)
        if cached:
            return Response({'success': True, 'language': lang_code, 'translations': cached, 'cached': True})
        language = Language.objects.filter(code=lang_code, is_active=True).first()
        if not language:
            return Response({'error': 'Language not found'}, status=status.HTTP_404_NOT_FOUND)
        translations = Translation.objects.filter(language=language, is_approved=True).select_related('key')
        data = {t.key.key: t.value for t in translations}
        cache.set(cache_key, data, 3600)
        return Response({'success': True, 'language': lang_code, 'translations': data, 'count': len(data)})


class LocalizedContentViewSet(viewsets.ModelViewSet):
    """LocalizedContent API — content per locale for CPAlead offers/pages"""
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['language', 'content_type', 'is_approved', 'review_status']
    search_fields = ['content_type', 'object_id', 'field_name']

    def get_queryset(self):
        from ..models.content import LocalizedContent
        qs = LocalizedContent.objects.select_related('language', 'approved_by')
        content_type = self.request.query_params.get('content_type')
        object_id = self.request.query_params.get('object_id')
        lang_code = self.request.query_params.get('lang')
        if content_type:
            qs = qs.filter(content_type=content_type)
        if object_id:
            qs = qs.filter(object_id=object_id)
        if lang_code:
            qs = qs.filter(language__code=lang_code)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers.localized_content import LocalizedContentSerializer
        return LocalizedContentSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def for_object(self, request):
        """content_type + object_id + lang দিয়ে content পাওয়া"""
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        lang_code = request.query_params.get('lang', 'en')
        if not content_type or not object_id:
            return Response({'error': 'content_type and object_id required'}, status=status.HTTP_400_BAD_REQUEST)
        from ..models.content import LocalizedContent
        contents = LocalizedContent.objects.filter(
            content_type=content_type, object_id=object_id,
            language__code=lang_code, is_approved=True
        ).select_related('language')
        data = {c.field_name: c.value for c in contents}
        return Response({'content_type': content_type, 'object_id': object_id, 'lang': lang_code, 'fields': data})

    @action(detail=False, methods=['post'])
    def bulk_set(self, request):
        """Multiple fields একসাথে set করা"""
        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        lang_code = request.data.get('lang', 'en')
        fields = request.data.get('fields', {})
        if not content_type or not object_id or not fields:
            return Response({'error': 'content_type, object_id, fields required'}, status=status.HTTP_400_BAD_REQUEST)
        from ..models.content import LocalizedContent
        from ..models.core import Language
        language = Language.objects.filter(code=lang_code, is_active=True).first()
        if not language:
            return Response({'error': f'Language {lang_code} not found'}, status=status.HTTP_404_NOT_FOUND)
        created = updated = 0
        for field_name, value in fields.items():
            _, was_created = LocalizedContent.objects.update_or_create(
                content_type=content_type, object_id=str(object_id),
                language=language, field_name=field_name,
                defaults={'value': value, 'is_approved': language.is_default}
            )
            if was_created:
                created += 1
            else:
                updated += 1
        return Response({'created': created, 'updated': updated, 'total': created + updated})


class LocalizedSEOViewSet(viewsets.ModelViewSet):
    """LocalizedSEO API — meta title/description per locale"""
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['language', 'content_type', 'is_indexable']

    def get_queryset(self):
        from ..models.content import LocalizedSEO
        return LocalizedSEO.objects.select_related('language').order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers.localized_content import LocalizedSEOSerializer
        return LocalizedSEOSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def for_object(self, request):
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        lang_code = request.query_params.get('lang', 'en')
        if not content_type or not object_id:
            return Response({'error': 'content_type and object_id required'}, status=status.HTTP_400_BAD_REQUEST)
        from ..models.content import LocalizedSEO
        seo = LocalizedSEO.objects.filter(
            content_type=content_type, object_id=object_id, language__code=lang_code
        ).first()
        if not seo:
            return Response({'error': 'SEO data not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'meta_title': seo.meta_title, 'meta_description': seo.meta_description,
            'og_title': seo.og_title, 'og_description': seo.og_description,
            'og_image_url': seo.og_image_url, 'is_indexable': seo.is_indexable,
            'hreflang_tags': seo.hreflang_tags, 'canonical_url': seo.canonical_url,
        })


class DateTimeFormatViewSet(viewsets.ReadOnlyModelViewSet):
    """DateTimeFormat API — date/time format per locale"""
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['language', 'calendar_system']

    def get_queryset(self):
        from ..models.settings import DateTimeFormat
        return DateTimeFormat.objects.select_related('language', 'country').order_by('language__code')

    def get_serializer_class(self):
        from ..serializers.settings import DateTimeFormatSerializer
        return DateTimeFormatSerializer

    @action(detail=False, methods=['get'])
    def for_locale(self, request):
        """lang_code + country_code দিয়ে format পাওয়া"""
        lang_code = request.query_params.get('lang', 'en')
        country_code = request.query_params.get('country', '')
        from ..models.settings import DateTimeFormat
        qs = DateTimeFormat.objects.filter(language__code=lang_code)
        if country_code:
            qs = qs.filter(country__code=country_code.upper())
        fmt = qs.first()
        if not fmt:
            return Response({'lang': lang_code, 'error': 'Format not found, using defaults',
                             'date_short': 'YYYY-MM-DD', 'time_short': 'HH:mm', 'first_day_of_week': 1})
        return Response({
            'lang': lang_code, 'country': country_code,
            'calendar': fmt.calendar_system,
            'date_short': fmt.date_short, 'date_medium': fmt.date_medium,
            'date_long': fmt.date_long, 'date_full': fmt.date_full,
            'time_short': fmt.time_short, 'time_medium': fmt.time_medium,
            'first_day_of_week': fmt.first_day_of_week,
            'am': fmt.am_symbol, 'pm': fmt.pm_symbol,
            'month_names': fmt.month_names, 'day_names': fmt.day_names,
            'day_names_short': fmt.day_names_short,
        })


class NumberFormatViewSet(viewsets.ReadOnlyModelViewSet):
    """NumberFormat API — decimal/thousands separator per locale"""
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['language']

    def get_queryset(self):
        from ..models.settings import NumberFormat
        return NumberFormat.objects.select_related('language', 'country')

    def get_serializer_class(self):
        from ..serializers.settings import NumberFormatSerializer
        return NumberFormatSerializer

    @action(detail=False, methods=['get'])
    def for_locale(self, request):
        lang_code = request.query_params.get('lang', 'en')
        from ..models.settings import NumberFormat
        fmt = NumberFormat.objects.filter(language__code=lang_code).first()
        if not fmt:
            return Response({'lang': lang_code, 'decimal': '.', 'thousands': ',', 'grouping': '3'})
        return Response({
            'lang': lang_code, 'decimal': fmt.decimal_symbol,
            'thousands': fmt.grouping_symbol, 'grouping': str(fmt.grouping_size),
            'secondary_grouping': fmt.secondary_grouping,
            'native_digits': fmt.native_digits,
            'percent': fmt.percent_symbol, 'number_system': fmt.number_system,
        })


class TranslationRequestViewSet(viewsets.ModelViewSet):
    """TranslationRequest API — request professional translation"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'source_language']
    search_fields = ['title', 'description', 'client']
    ordering_fields = ['created_at', 'due_date', 'priority']

    def get_queryset(self):
        from ..models.content import TranslationRequest
        qs = TranslationRequest.objects.select_related('source_language', 'requested_by', 'assigned_to')
        if not self.request.user.is_staff:
            qs = qs.filter(requested_by=self.request.user)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers.localized_content import TranslationRequestSerializer
        return TranslationRequestSerializer

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def assign(self, request, pk=None):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        req = self.get_object()
        user_id = request.data.get('user_id')
        user = User.objects.filter(pk=user_id).first()
        if not user:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        req.assigned_to = user
        req.status = 'assigned'
        req.save(update_fields=['assigned_to', 'status'])
        return Response({'assigned_to': user.email, 'status': req.status})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        req = self.get_object()
        req.status = 'completed'
        from django.utils import timezone
        req.completed_at = timezone.now()
        req.save(update_fields=['status', 'completed_at'])
        return Response({'status': 'completed'})


class LocalizationConfigViewSet(viewsets.ModelViewSet):
    """LocalizationConfig API — tenant-level localization settings"""
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['tenant_id']

    def get_queryset(self):
        from ..models.settings import LocalizationConfig
        return LocalizationConfig.objects.select_related('default_language', 'default_currency').order_by('tenant_id')

    def get_serializer_class(self):
        from ..serializers.settings import LocalizationConfigSerializer
        return LocalizationConfigSerializer

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def public(self, request, pk=None):
        """Public non-sensitive config — frontend can fetch this"""
        config = self.get_object()
        return Response({
            'tenant_id': config.tenant_id,
            'default_language': config.default_language.code if config.default_language else 'en',
            'default_currency': config.default_currency.code if config.default_currency else 'USD',
            'supported_languages': list(config.supported_languages.values_list('code', flat=True)),
            'detect_from_browser': config.detect_language_from_browser,
            'detect_from_ip': config.detect_language_from_ip,
            'show_untranslated_keys': config.show_untranslated_keys,
            'enable_rtl': config.enable_rtl_support,
            'cache_ttl': config.translation_cache_ttl,
        })


class UserPreferenceViewSet(viewsets.ViewSet):
    """UserPreference full API — wraps the expanded UserPreferenceService"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def my(self, request):
        """Current user-এর full preference"""
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        service = UserPreferenceService()
        prefs = service.get_full_preference(request.user)
        return Response({'success': True, 'data': prefs})

    @action(detail=False, methods=['post'])
    def set_language(self, request):
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        lang_code = request.data.get('language_code')
        pref_type = request.data.get('type', 'ui')
        if not lang_code:
            return Response({'error': 'language_code required'}, status=status.HTTP_400_BAD_REQUEST)
        service = UserPreferenceService()
        result = service.set_language(request.user, lang_code, pref_type)
        return Response(result)

    @action(detail=False, methods=['post'])
    def set_currency(self, request):
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        currency_code = request.data.get('currency_code')
        if not currency_code:
            return Response({'error': 'currency_code required'}, status=status.HTTP_400_BAD_REQUEST)
        result = UserPreferenceService().set_currency(request.user, currency_code)
        return Response(result)

    @action(detail=False, methods=['post'])
    def set_timezone(self, request):
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        tz_name = request.data.get('timezone')
        if not tz_name:
            return Response({'error': 'timezone required'}, status=status.HTTP_400_BAD_REQUEST)
        result = UserPreferenceService().set_timezone(request.user, tz_name)
        return Response(result)

    @action(detail=False, methods=['post'])
    def set_date_format(self, request):
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        date_fmt = request.data.get('date_format')
        time_fmt = request.data.get('time_format')
        if not date_fmt:
            return Response({'error': 'date_format required'}, status=status.HTTP_400_BAD_REQUEST)
        result = UserPreferenceService().set_date_format(request.user, date_fmt, time_fmt)
        return Response(result)

    @action(detail=False, methods=['post'])
    def detect(self, request):
        """IP + browser থেকে auto-detect করে preference set"""
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().detect_and_set_from_request(request.user, request)
        return Response(result)

    @action(detail=False, methods=['post'])
    def reset(self, request):
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        result = UserPreferenceService().reset_to_defaults(request.user)
        return Response(result)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def distribution(self, request):
        """Admin: সব users-এর language distribution"""
        from ..services.services_loca.UserPreferenceService import UserPreferenceService
        data = UserPreferenceService().get_language_distribution()
        return Response({'distribution': data})



    @action(detail=False, methods=['get'], url_path='ota-checksum/(?P<language>[^/.]+)')
    def ota_checksum(self, request, language=None):
        """OTA update polling — frontend compares checksum to detect new translations"""
        from ..services.translation.LanguagePackBuilder import LanguagePackBuilder
        result = LanguagePackBuilder().build(language or 'en', approved_only=True, include_metadata=False)
        if not result['success']:
            return Response({'checksum': '', 'count': 0})
        return Response({
            'language': language,
            'checksum': result['checksum'],
            'count': result['count'],
            'coverage': result['coverage'],
        })

class InsightViewSet(viewsets.ReadOnlyModelViewSet):
    """LocalizationInsight analytics viewset"""
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['language', 'country', 'date']
    ordering_fields = ['date', 'total_requests']

    def get_queryset(self):
        from ..models.analytics import LocalizationInsight
        return LocalizationInsight.objects.select_related('language', 'country').order_by('-date')

    def get_serializer_class(self):
        from ..serializers.analytics import LocalizationInsightSerializer
        return LocalizationInsightSerializer

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from ..models.analytics import LocalizationInsight
        from django.db.models import Sum, Avg
        from django.utils import timezone
        from datetime import timedelta
        cutoff = (timezone.now() - timedelta(days=30)).date()
        agg = LocalizationInsight.objects.filter(date__gte=cutoff).aggregate(
            total_requests=Sum('total_requests'),
            total_hits=Sum('translation_hits'),
            total_misses=Sum('translation_misses'),
            avg_response=Avg('avg_response_time_ms'),
            total_conversions=Sum('currency_conversions'),
        )
        return Response({'success': True, 'period_days': 30, 'data': agg})

    @action(detail=False, methods=['get'])
    def by_language(self, request):
        from ..models.analytics import LocalizationInsight
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        days = int(request.query_params.get('days', 30))
        cutoff = (timezone.now() - timedelta(days=days)).date()
        data = list(
            LocalizationInsight.objects.filter(date__gte=cutoff, language__isnull=False)
            .values('language__code', 'language__name', 'language__flag_emoji')
            .annotate(total=Sum('total_requests'), users=Sum('unique_users'))
            .order_by('-total')[:20]
        )
        return Response({'success': True, 'period_days': days, 'data': data})

    @action(detail=False, methods=['get'])
    def by_country(self, request):
        from ..models.analytics import GeoInsight
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        days = int(request.query_params.get('days', 30))
        cutoff = (timezone.now() - timedelta(days=days)).date()
        data = list(
            GeoInsight.objects.filter(date__gte=cutoff)
            .values('country_code')
            .annotate(total_users=Sum('total_users'), total_requests=Sum('total_requests'))
            .order_by('-total_users')[:20]
        )
        return Response({'success': True, 'period_days': days, 'data': data})


class AdminLocalizationViewSet(viewsets.ViewSet):
    """Admin-only bulk operations"""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['post'])
    def clear_all_cache(self, request):
        from django.core.cache import cache
        try:
            cache.clear()
            return Response({'success': True, 'message': 'All localization cache cleared'})
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def recalculate_coverage(self, request):
        from ..services.translation.TranslationCoverageService import TranslationCoverageService
        results = TranslationCoverageService().calculate_all()
        return Response({'success': True, 'languages': len(results), 'results': results})

    @action(detail=False, methods=['post'])
    def run_qa_all(self, request):
        from ..services.translation.TranslationQAService import TranslationQAService
        from ..models.core import Language
        service = TranslationQAService()
        langs = Language.objects.filter(is_active=True, is_default=False)
        all_results = {}
        for lang in langs:
            result = service.run_batch_qa(lang.code)
            all_results[lang.code] = {
                'total': result.get('total', 0), 'failed': result.get('failed', 0),
                'warnings': result.get('warnings', 0),
            }
        return Response({'success': True, 'results': all_results})

    @action(detail=False, methods=['post'])
    def update_exchange_rates(self, request):
        from ..services.services_loca.CurrencyService import CurrencyService
        provider = request.data.get('provider', 'exchangerate-api')
        result = CurrencyService().update_rates_from_external(provider)
        return Response(result)

    @action(detail=False, methods=['get'])
    def system_health(self, request):
        from django.utils import timezone
        health = {'timestamp': timezone.now().isoformat(), 'checks': {}}
        try:
            from ..models.core import Language
            health['checks']['database'] = {'ok': True, 'languages': Language.objects.count()}
        except Exception as e:
            health['checks']['database'] = {'ok': False, 'error': str(e)}
        try:
            from django.core.cache import cache
            cache.set('health_test', 'ok', 5)
            health['checks']['cache'] = {'ok': cache.get('health_test') == 'ok'}
        except Exception as e:
            health['checks']['cache'] = {'ok': False, 'error': str(e)}
        try:
            from ..services.providers.ProviderHealthChecker import ProviderHealthChecker
            health['checks']['providers'] = ProviderHealthChecker().check_all()
        except Exception as e:
            health['checks']['providers'] = {'ok': False, 'error': str(e)}
        health['all_ok'] = all(v.get('ok', False) if isinstance(v, dict) else False
                               for v in health['checks'].values())
        return Response(health)


class WorkflowViewSet(viewsets.ViewSet):
    """Translation workflow — submit, review, approve, reject"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"])
    def submit(self, request):
        """Translator translation submit করে"""
        from ..services.translation.TranslatorWorkflowService import TranslatorWorkflowService
        result = TranslatorWorkflowService().submit_translation(
            key=request.data.get("key", ""),
            language_code=request.data.get("language", ""),
            value=request.data.get("value", ""),
            translator_user=request.user,
            comment=request.data.get("comment", ""),
        )
        return Response(result)

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def review(self, request):
        """Reviewer approve/reject করে"""
        from ..services.translation.TranslatorWorkflowService import TranslatorWorkflowService
        result = TranslatorWorkflowService().review_translation(
            translation_id=request.data.get("translation_id"),
            decision=request.data.get("decision", "approve"),
            reviewer_user=request.user,
            comment=request.data.get("comment", ""),
        )
        return Response(result)

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Pending review translations"""
        from ..services.translation.TranslatorWorkflowService import TranslatorWorkflowService
        lang = request.query_params.get("language")
        data = TranslatorWorkflowService().get_pending_reviews(language_code=lang)
        return Response({"count": len(data), "results": data})

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def bulk_approve(self, request):
        """High quality-score translations bulk approve"""
        from ..services.translation.TranslatorWorkflowService import TranslatorWorkflowService
        result = TranslatorWorkflowService().bulk_approve(
            language_code=request.data.get("language", ""),
            min_quality_score=float(request.data.get("min_quality_score", 85.0)),
            reviewer=request.user,
        )
        return Response(result)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Workflow stats for a language"""
        from ..services.translation.TranslatorWorkflowService import TranslatorWorkflowService
        lang = request.query_params.get("language", "en")
        return Response(TranslatorWorkflowService().get_workflow_stats(lang))


class QualityViewSet(viewsets.ViewSet):
    """Translation quality — MTQE + LQA scoring"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"])
    def mtqe(self, request):
        """Machine Translation Quality Estimation"""
        from ..services.translation.MTQEService import MTQEService
        result = MTQEService().estimate(
            source=request.data.get("source", ""),
            translated=request.data.get("translated", ""),
            source_lang=request.data.get("source_lang", "en"),
            target_lang=request.data.get("target_lang", "bn"),
        )
        return Response(result)

    @action(detail=False, methods=["post"])
    def lqa(self, request):
        """Linguistic Quality Assurance scoring"""
        from ..services.translation.LQAService import LQAService
        result = LQAService().evaluate(
            source=request.data.get("source", ""),
            translated=request.data.get("translated", ""),
            source_lang=request.data.get("source_lang", "en"),
            target_lang=request.data.get("target_lang", "bn"),
        )
        return Response(result)

    @action(detail=False, methods=["get"])
    def mt_cost_report(self, request):
        """MT cost report — last 30 days"""
        from ..services.translation.MTCostTracker import MTCostTracker
        return Response(MTCostTracker().get_monthly_report())


class NamespaceViewSet(viewsets.ViewSet):
    """Namespace lazy loading — per-namespace translation packs"""
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def pack(self, request):
        """Single namespace pack"""
        from ..services.translation.NamespaceLazyLoader import NamespaceLazyLoader
        lang = request.query_params.get("lang", "en")
        namespace = request.query_params.get("namespace", "common")
        version = request.query_params.get("version", "v1")
        result = NamespaceLazyLoader().get_namespace_pack(lang, namespace, version)
        return Response(result)

    @action(detail=False, methods=["get"])
    def list_namespaces(self, request):
        """Available namespaces + key counts"""
        from ..services.translation.NamespaceLazyLoader import NamespaceLazyLoader
        lang = request.query_params.get("lang", "en")
        return Response({"language": lang, "namespaces": NamespaceLazyLoader().get_all_namespaces(lang)})


class CPALeadViewSet(viewsets.ViewSet):
    """CPAlead-specific localization endpoints"""
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def payment_methods(self, request):
        """Country-এর available payment methods"""
        from ..services.cpalead.CountryTargetingService import CountryTargetingService
        country = request.query_params.get("country", "BD")
        return Response({
            "country": country,
            "methods": CountryTargetingService().get_payment_methods(country),
        })

    @action(detail=False, methods=["get"])
    def earning_config(self, request):
        """Country-এর earning/withdrawal config"""
        from ..services.cpalead.CountryTargetingService import CountryTargetingService
        country = request.query_params.get("country", "BD")
        return Response(CountryTargetingService().get_earning_config(country))

    @action(detail=False, methods=["get"])
    def seo_meta(self, request):
        """Localized SEO meta tags"""
        from ..services.cpalead.LocalizedSEOService import LocalizedSEOService
        page = request.query_params.get("page", "home")
        lang = request.query_params.get("lang", "en")
        ctx = {"id": request.query_params.get("id", ""), "title": "", "description": ""}
        return Response(LocalizedSEOService().get_localized_meta(page, lang, ctx))

    @action(detail=False, methods=["get"])
    def locale_analytics(self, request):
        """Conversion rates by language"""
        from ..services.cpalead.LocaleAnalyticsService import LocaleAnalyticsService
        days = int(request.query_params.get("days", 30))
        return Response({
            "by_language": LocaleAnalyticsService().get_conversion_by_language(days),
            "by_country": LocaleAnalyticsService().get_revenue_by_country(days),
        })

    @action(detail=False, methods=["post"])
    def is_offer_available(self, request):
        """Offer কি এই country-তে available?"""
        from ..services.cpalead.CountryTargetingService import CountryTargetingService
        offer_id = request.data.get("offer_id", 0)
        country = request.data.get("country", "BD")
        available = CountryTargetingService().is_offer_available(offer_id, country)
        return Response({"offer_id": offer_id, "country": country, "available": available})


class ScreenshotViewSet(viewsets.ViewSet):
    """Screenshot/Visual Context — Phrase.com screenshot feature equivalent"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def upload(self, request):
        from ..services.screenshot_service import ScreenshotService
        result = ScreenshotService().upload_screenshot(
            image_data=request.data.get('image_data', ''),
            image_url=request.data.get('image_url', ''),
            page_url=request.data.get('page_url', ''),
            title=request.data.get('title', ''),
            component=request.data.get('component', ''),
            key_names=request.data.get('key_names', []),
            uploaded_by=request.user,
            region=request.data.get('region'),
        )
        code = status.HTTP_201_CREATED if result['success'] else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    @action(detail=False, methods=['get'])
    def for_key(self, request):
        key_name = request.query_params.get('key')
        if not key_name:
            return Response({'error': 'key required'}, status=status.HTTP_400_BAD_REQUEST)
        from ..services.screenshot_service import ScreenshotService
        shots = ScreenshotService().get_for_key(key_name)
        return Response({'key': key_name, 'screenshots': shots, 'count': len(shots)})

    @action(detail=False, methods=['get'])
    def keys_without_screenshots(self, request):
        from ..services.screenshot_service import ScreenshotService
        keys = ScreenshotService().get_keys_without_screenshots(
            limit=int(request.query_params.get('limit', 50))
        )
        return Response({'keys': keys, 'count': len(keys)})

    @action(detail=False, methods=['post'])
    def link_keys(self, request):
        from ..services.screenshot_service import ScreenshotService
        result = ScreenshotService().bulk_link_keys(
            request.data.get('screenshot_id'), request.data.get('key_names', [])
        )
        return Response(result)


class GitWebhookViewSet(viewsets.ViewSet):
    """Git webhook endpoint — GitHub/GitLab push events process করে"""

    @action(detail=False, methods=['post'])
    def github(self, request):
        """GitHub push webhook"""
        from django.conf import settings
        from ..services.git_integration_service import GitWebhookService
        secret = getattr(settings, 'GITHUB_WEBHOOK_SECRET', '')
        if secret:
            sig = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
            if not GitWebhookService().verify_signature(request.body, sig, secret):
                return Response({'error': 'Invalid signature'}, status=status.HTTP_403_FORBIDDEN)
        result = GitWebhookService().process_push_event(request.data)
        return Response(result)

    @action(detail=False, methods=['post'])
    def gitlab(self, request):
        """GitLab push webhook"""
        from django.conf import settings
        from ..services.git_integration_service import GitWebhookService
        token = getattr(settings, 'GITLAB_WEBHOOK_TOKEN', '')
        if token and request.META.get('HTTP_X_GITLAB_TOKEN') != token:
            return Response({'error': 'Invalid token'}, status=status.HTTP_403_FORBIDDEN)
        # Normalize GitLab payload to GitHub format
        payload = {
            'commits': request.data.get('commits', []),
            'repository': {'name': request.data.get('project', {}).get('name', '')},
            'ref': request.data.get('ref', ''),
            'after': request.data.get('after', ''),
        }
        result = GitWebhookService().process_push_event(payload)
        return Response(result)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def sync_keys(self, request):
        """Manual key sync — directory scan করে DB-তে sync করে"""
        from ..services.git_integration_service import KeyExtractor, GitWebhookService
        directory = request.data.get('directory', '.')
        namespace = request.data.get('namespace', '')
        extractor = KeyExtractor()
        file_results = extractor.extract_from_directory(directory)
        all_keys = set()
        for keys in file_results.values():
            all_keys.update(keys)
        result = GitWebhookService().sync_keys_to_db(all_keys, namespace)
        result['files_scanned'] = len(file_results)
        return Response(result)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def export_file(self, request):
        """Translation file export — repo-তে commit করার জন্য"""
        from ..services.git_integration_service import GitWebhookService
        language = request.query_params.get('lang', 'en')
        fmt = request.query_params.get('format', 'json')
        content = GitWebhookService().generate_translation_file(language, fmt)
        content_types = {'json': 'application/json', 'po': 'text/plain', 'xliff': 'application/xml'}
        filenames = {'json': f'{language}.json', 'po': f'{language}.po', 'xliff': f'{language}.xliff'}
        from django.http import HttpResponse
        return HttpResponse(
            content, content_type=content_types.get(fmt, 'text/plain'),
            headers={'Content-Disposition': f'attachment; filename="{filenames.get(fmt, f"{language}.txt")}"'}
        )


class ContentRegionViewSet(viewsets.ViewSet):
    """CPAlead ContentRegion — country-based feature flags"""
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def for_country(self, request):
        """Country code দিয়ে region info পাওয়া"""
        from ..services.cpalead.ContentRegionService import ContentRegionService
        country = request.query_params.get('country', '')
        if not country:
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            if ip:
                try:
                    from ..services.services_loca.GeoService import GeoService
                    geo = GeoService().detect_from_ip(ip.split(',')[0].strip())
                    country = geo.get('country_code', '')
                except Exception:
                    pass
        if not country:
            return Response({'error': 'country param required'}, status=status.HTTP_400_BAD_REQUEST)
        result = ContentRegionService().get_localized_offer_config(country)
        return Response(result)

    @action(detail=False, methods=['get'])
    def feature(self, request):
        """Country-তে feature enabled কিনা"""
        from ..services.cpalead.ContentRegionService import ContentRegionService
        country = request.query_params.get('country', '')
        feature = request.query_params.get('feature', '')
        if not country or not feature:
            return Response({'error': 'country and feature params required'}, status=status.HTTP_400_BAD_REQUEST)
        enabled = ContentRegionService().is_feature_enabled(country, feature)
        return Response({'country': country, 'feature': feature, 'enabled': enabled})

    @action(detail=False, methods=['get'])
    def payment_methods(self, request):
        """Country-র payment methods"""
        from ..services.cpalead.ContentRegionService import ContentRegionService
        country = request.query_params.get('country', 'US')
        methods = ContentRegionService().get_payment_methods(country)
        return Response({'country': country, 'payment_methods': methods})

    @action(detail=False, methods=['get'])
    def gdpr_consent(self, request):
        """GDPR consent text"""
        from ..services.cpalead.ContentRegionService import ContentRegionService
        country = request.query_params.get('country', '')
        lang = request.query_params.get('lang', 'en')
        requires = ContentRegionService().requires_gdpr(country)
        text = ContentRegionService().get_gdpr_consent_text(country, lang) if requires else None
        return Response({'country': country, 'requires_gdpr': requires, 'consent_text': text})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """All regions summary"""
        from ..services.cpalead.ContentRegionService import ContentRegionService
        return Response(ContentRegionService().get_all_regions_summary())
