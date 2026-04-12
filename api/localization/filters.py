# filters.py — Custom DjangoFilterBackend FilterSets
import django_filters
from django.db.models import Q
from django_filters.rest_framework import FilterSet, filters


class LanguageFilter(FilterSet):
    is_rtl = filters.BooleanFilter()
    is_active = filters.BooleanFilter()
    is_default = filters.BooleanFilter()
    search = filters.CharFilter(method='filter_search')
    script = filters.CharFilter(field_name='script_code', lookup_expr='iexact')

    def filter_search(self, qs, name, value):
        return qs.filter(Q(name__icontains=value) | Q(name_native__icontains=value) | Q(code__icontains=value))

    class Meta:
        from .models.core import Language
        model = Language
        fields = ['is_rtl', 'is_active', 'is_default', 'script_code']


class TranslationFilter(FilterSet):
    language   = filters.CharFilter(field_name='language__code', lookup_expr='iexact')
    key        = filters.CharFilter(field_name='key__key', lookup_expr='icontains')
    category   = filters.CharFilter(field_name='key__category', lookup_expr='iexact')
    namespace  = filters.CharFilter(field_name='key__namespace', lookup_expr='iexact')
    is_approved = filters.BooleanFilter()
    source     = filters.CharFilter(field_name='source', lookup_expr='iexact')
    quality    = filters.CharFilter(field_name='quality_score', lookup_expr='iexact')
    min_quality = filters.NumberFilter(field_name='quality_score_numeric', lookup_expr='gte')
    search     = filters.CharFilter(method='filter_search')
    date_from  = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    date_to    = filters.DateFilter(field_name='created_at', lookup_expr='lte')

    def filter_search(self, qs, name, value):
        return qs.filter(Q(value__icontains=value) | Q(key__key__icontains=value))

    class Meta:
        from .models.core import Translation
        model = Translation
        fields = ['language', 'is_approved', 'source', 'quality_score']


class CountryFilter(FilterSet):
    continent = filters.CharFilter(field_name='continent', lookup_expr='iexact')
    region    = filters.CharFilter(field_name='region', lookup_expr='icontains')
    is_eu     = filters.BooleanFilter(field_name='is_eu_member')
    gdpr      = filters.BooleanFilter(field_name='requires_gdpr')
    search    = filters.CharFilter(method='filter_search')
    driving_side = filters.CharFilter(field_name='driving_side', lookup_expr='iexact')

    def filter_search(self, qs, name, value):
        return qs.filter(Q(name__icontains=value) | Q(native_name__icontains=value) | Q(code__iexact=value))

    class Meta:
        from .models.core import Country
        model = Country
        fields = ['continent', 'is_eu_member', 'requires_gdpr', 'driving_side']


class CurrencyFilter(FilterSet):
    is_active  = filters.BooleanFilter()
    is_default = filters.BooleanFilter()
    is_crypto  = filters.BooleanFilter()
    search     = filters.CharFilter(method='filter_search')

    def filter_search(self, qs, name, value):
        return qs.filter(Q(code__icontains=value) | Q(name__icontains=value) | Q(symbol__icontains=value))

    class Meta:
        from .models.core import Currency
        model = Currency
        fields = ['is_active', 'is_default', 'is_crypto']


class MissingTranslationFilter(FilterSet):
    language   = filters.CharFilter(field_name='language__code', lookup_expr='iexact')
    resolved   = filters.BooleanFilter()
    priority   = filters.CharFilter()
    date_from  = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    date_to    = filters.DateFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        from .models.translation import MissingTranslation
        model = MissingTranslation
        fields = ['language', 'resolved', 'priority']


class TranslationMemoryFilter(FilterSet):
    src_lang   = filters.CharFilter(field_name='source_language__code', lookup_expr='iexact')
    tgt_lang   = filters.CharFilter(field_name='target_language__code', lookup_expr='iexact')
    domain     = filters.CharFilter(field_name='domain', lookup_expr='iexact')
    is_approved = filters.BooleanFilter()
    min_quality = filters.NumberFilter(field_name='quality_rating', lookup_expr='gte')
    search     = filters.CharFilter(method='filter_search')

    def filter_search(self, qs, name, value):
        return qs.filter(Q(source_text__icontains=value) | Q(target_text__icontains=value))

    class Meta:
        from .models.translation import TranslationMemory
        model = TranslationMemory
        fields = ['source_language', 'target_language', 'domain', 'is_approved']


class GlossaryFilter(FilterSet):
    src_lang   = filters.CharFilter(field_name='source_language__code', lookup_expr='iexact')
    domain     = filters.CharFilter()
    is_dnt     = filters.BooleanFilter(field_name='is_do_not_translate')
    is_brand   = filters.BooleanFilter(field_name='is_brand_term')
    search     = filters.CharFilter(method='filter_search')

    def filter_search(self, qs, name, value):
        return qs.filter(Q(source_term__icontains=value) | Q(definition__icontains=value))

    class Meta:
        from .models.translation import TranslationGlossary
        model = TranslationGlossary
        fields = ['source_language', 'domain', 'is_do_not_translate', 'is_brand_term']


class ExchangeRateFilter(FilterSet):
    from_currency = filters.CharFilter(field_name='from_currency__code', lookup_expr='iexact')
    to_currency   = filters.CharFilter(field_name='to_currency__code', lookup_expr='iexact')
    source        = filters.CharFilter()
    date_from     = filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to       = filters.DateFilter(field_name='date', lookup_expr='lte')
    is_official   = filters.BooleanFilter()

    class Meta:
        from .models.currency import ExchangeRate
        model = ExchangeRate
        fields = ['from_currency', 'to_currency', 'source', 'is_official']


class LocalizedContentFilter(FilterSet):
    content_type = filters.CharFilter()
    object_id    = filters.CharFilter()
    language     = filters.CharFilter(field_name='language__code', lookup_expr='iexact')
    is_approved  = filters.BooleanFilter()
    review_status = filters.CharFilter()
    is_machine   = filters.BooleanFilter(field_name='is_machine_translated')

    class Meta:
        from .models.content import LocalizedContent
        model = LocalizedContent
        fields = ['content_type', 'object_id', 'language', 'is_approved', 'review_status']


class AnalyticsFilter(FilterSet):
    language     = filters.CharFilter(field_name='language__code', lookup_expr='iexact')
    country      = filters.CharFilter(field_name='country_code', lookup_expr='iexact')
    event_type   = filters.CharFilter()
    date_from    = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to      = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        from .models.analytics import LocalizationInsight
        model = LocalizationInsight
        fields = ['language', 'country', 'date']
