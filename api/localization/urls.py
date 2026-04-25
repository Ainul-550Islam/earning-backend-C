# urls.py — World #1 Localization System — সব 30+ routes
from django.urls import path, include
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from rest_framework.routers import SimpleRouter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# ViewSets
from .viewsets import (
    LocalizedContentViewSet, LocalizedSEOViewSet, DateTimeFormatViewSet,
    NumberFormatViewSet, TranslationRequestViewSet, LocalizationConfigViewSet,
    UserPreferenceViewSet,
    InsightViewSet, AdminLocalizationViewSet,
    ScreenshotViewSet,
    GitWebhookViewSet,
    ContentRegionViewSet,
    WorkflowViewSet, QualityViewSet, NamespaceViewSet, CPALeadViewSet,
    LanguageViewSet, TranslationViewSet, TranslationKeyViewSet,
    MissingTranslationViewSet, TranslationCacheViewSet,
    CountryViewSet, CurrencyViewSet, TimezoneViewSet, CityViewSet,
    ExchangeRateViewSet, TranslationMemoryViewSet, TranslationGlossaryViewSet,
    TranslationCoverageViewSet, GeoIPViewSet, AutoTranslateViewSet, PublicViewSet,
)

router = SimpleRouter()
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'translation-keys', TranslationKeyViewSet, basename='translation-key')
router.register(r'translations', TranslationViewSet, basename='translation')
router.register(r'missing-translations', MissingTranslationViewSet, basename='missing-translation')
router.register(r'translation-cache', TranslationCacheViewSet, basename='translation-cache')
router.register(r'countries', CountryViewSet, basename='country')
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'timezones', TimezoneViewSet, basename='timezone')
router.register(r'cities', CityViewSet, basename='city')
router.register(r'exchange-rates', ExchangeRateViewSet, basename='exchange-rate')
router.register(r'translation-memory', TranslationMemoryViewSet, basename='translation-memory')
router.register(r'glossary', TranslationGlossaryViewSet, basename='glossary')
router.register(r'coverage', TranslationCoverageViewSet, basename='coverage')
router.register(r'geoip', GeoIPViewSet, basename='geoip')
router.register(r'auto-translate', AutoTranslateViewSet, basename='auto-translate')
router.register(r'public', PublicViewSet, basename='public')
router.register(r'localized-content', LocalizedContentViewSet, basename='localized-content')
router.register(r'localized-seo', LocalizedSEOViewSet, basename='localized-seo')
router.register(r'datetime-formats', DateTimeFormatViewSet, basename='datetime-format')
router.register(r'number-formats', NumberFormatViewSet, basename='number-format')
router.register(r'translation-requests', TranslationRequestViewSet, basename='translation-request')
router.register(r'localization-config', LocalizationConfigViewSet, basename='localization-config')
router.register(r'user-preferences', UserPreferenceViewSet, basename='user-preference')
router.register(r'regions', ContentRegionViewSet, basename='region')
router.register(r'git', GitWebhookViewSet, basename='git')
router.register(r'screenshots', ScreenshotViewSet, basename='screenshot')
router.register(r'insights', InsightViewSet, basename='insight')
router.register(r'admin-localization', AdminLocalizationViewSet, basename='admin-localization')
router.register(r'workflow', WorkflowViewSet, basename='workflow')
router.register(r'quality', QualityViewSet, basename='quality')
router.register(r'namespaces', NamespaceViewSet, basename='namespace')
router.register(r'cpalead', CPALeadViewSet, basename='cpalead')


@require_http_methods(["GET"])
def health_check(request):
    from .models.core import Language
    services = {}
    try:
        language_count = Language.objects.count()
        services['database'] = {'status': 'ok', 'records': language_count}
    except Exception as e:
        services['database'] = {'status': 'error', 'error': str(e)}
    return JsonResponse({'success': True, 'data': {'status': 'healthy', 'version': '2.0', 'timestamp': timezone.now().isoformat(), 'services': services}})


@require_http_methods(["GET"])
def api_docs(request):
    return JsonResponse({'success': True, 'data': {
        'name': 'World #1 Localization API', 'version': 'v2',
        'models': 38, 'endpoints': 95,
        'features': ['Translation Memory', 'Glossary', 'GeoIP', 'Auto-translate', 'Coverage', 'QA', 'Import/Export'],
    }}, json_dumps_params={'indent': 2})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_translations(request, language_code):
    from .models.core import Language, Translation
    language = Language.objects.filter(code=language_code, is_active=True).first()
    if not language:
        return Response({'error': 'Language not found'}, status=404)
    translations = Translation.objects.filter(language=language, is_approved=True).select_related('key')
    data = {t.key.key: t.value for t in translations}
    return Response({'language': language.name, 'code': language.code, 'translations': data, 'count': len(data)})


@api_view(['POST'])
@permission_classes([AllowAny])
def report_missing_translation(request):
    from .models.translation import MissingTranslation
    key = request.data.get('key')
    language_code = request.data.get('language_code')
    if not key or not language_code:
        return Response({'error': 'Key and language_code required'}, status=400)
    MissingTranslation.log_missing(key=key, language_code=language_code, request=request)
    return Response({'message': 'Reported successfully'}, status=201)


urlpatterns = [
    path('', include(router.urls)),
    # Original endpoints (backward compat)
    path('public/translations/<str:language_code>/', get_translations, name='public-translations'),
    path('report-missing/', report_missing_translation, name='report-missing-translation'),
    # System
    path('health/', health_check, name='health-check'),
    path('docs/', api_docs, name='api-docs'),
]
