# publisher_tools/serializers_abtest.py
# ============================================================
# NEW FILE — Serializers for ABTest + ABTestVariant
# ============================================================
from decimal import Decimal
from rest_framework import serializers
from .models import ABTest, ABTestVariant


class ABTestVariantSerializer(serializers.ModelSerializer):
    revenue_per_impression = serializers.SerializerMethodField()

    class Meta:
        model  = ABTestVariant
        fields = [
            'id', 'name', 'is_control', 'traffic_split', 'config',
            'total_impressions', 'total_clicks', 'total_revenue',
            'total_ad_requests', 'ecpm', 'ctr', 'fill_rate',
            'revenue_per_impression',
        ]
        read_only_fields = [
            'id', 'total_impressions', 'total_clicks', 'total_revenue',
            'total_ad_requests', 'ecpm', 'ctr', 'fill_rate',
        ]

    def get_revenue_per_impression(self, obj):
        if obj.total_impressions > 0:
            return round(float(obj.total_revenue) / obj.total_impressions, 6)
        return 0.0


class ABTestListSerializer(serializers.ModelSerializer):
    publisher_id     = serializers.CharField(source='publisher.publisher_id', read_only=True)
    ad_unit_id       = serializers.CharField(source='ad_unit.unit_id',       read_only=True)
    variant_count    = serializers.SerializerMethodField()
    total_impressions = serializers.SerializerMethodField()

    class Meta:
        model  = ABTest
        fields = [
            'id', 'test_id', 'name', 'test_type', 'status',
            'publisher_id', 'ad_unit_id',
            'start_date', 'end_date', 'min_duration_days',
            'confidence_level', 'confidence_achieved',
            'variant_count', 'total_impressions',
            'winner_reason', 'concluded_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_variant_count(self, obj):
        return obj.variants.count()

    def get_total_impressions(self, obj):
        from django.db.models import Sum
        agg = obj.variants.aggregate(total=Sum('total_impressions'))
        return agg.get('total') or 0


class ABTestDetailSerializer(serializers.ModelSerializer):
    variants         = ABTestVariantSerializer(many=True, read_only=True)
    publisher_id     = serializers.CharField(source='publisher.publisher_id', read_only=True)
    ad_unit_id       = serializers.CharField(source='ad_unit.unit_id',       read_only=True)
    ad_unit_name     = serializers.CharField(source='ad_unit.name',           read_only=True)
    winner_variant   = ABTestVariantSerializer(read_only=True)

    class Meta:
        model  = ABTest
        fields = [
            'id', 'test_id', 'name', 'hypothesis', 'description',
            'test_type', 'status',
            'publisher_id', 'ad_unit_id', 'ad_unit_name',
            'start_date', 'end_date', 'min_duration_days',
            'confidence_level', 'min_sample_size',
            'confidence_achieved', 'statistical_significance',
            'winner_variant', 'winner_reason', 'conclusion_notes',
            'concluded_at', 'metadata',
            'variants',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'test_id', 'publisher_id', 'ad_unit_id', 'ad_unit_name',
            'confidence_achieved', 'statistical_significance',
            'winner_variant', 'concluded_at', 'variants',
            'created_at', 'updated_at',
        ]


class ABTestVariantCreateSerializer(serializers.Serializer):
    """Nested variant data for ABTestCreateSerializer."""
    name          = serializers.CharField(max_length=100)
    is_control    = serializers.BooleanField(default=False)
    traffic_split = serializers.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=Decimal('1'), max_value=Decimal('99'),
    )
    config = serializers.DictField(default=dict)


class ABTestCreateSerializer(serializers.ModelSerializer):
    """Write serializer — create an A/B test with variants."""
    variants = ABTestVariantCreateSerializer(many=True, write_only=True)

    class Meta:
        model  = ABTest
        fields = [
            'name', 'hypothesis', 'description',
            'test_type', 'ad_unit',
            'min_duration_days', 'confidence_level', 'min_sample_size',
            'metadata', 'variants',
        ]

    def validate_test_type(self, value):
        valid = [c[0] for c in ABTest._meta.get_field('test_type').choices]
        if value not in valid:
            raise serializers.ValidationError(
                f'Invalid test_type {value!r}. Valid: {valid}'
            )
        return value

    def validate_variants(self, variants):
        if len(variants) < 2:
            raise serializers.ValidationError(
                'Minimum 2 variants required (1 control + 1 treatment).'
            )
        controls = [v for v in variants if v.get('is_control')]
        if len(controls) != 1:
            raise serializers.ValidationError(
                f'Exactly 1 control variant required. Got {len(controls)}.'
            )
        total = sum(Decimal(str(v.get('traffic_split', 0))) for v in variants)
        if abs(total - Decimal('100.00')) > Decimal('0.01'):
            raise serializers.ValidationError(
                f'Variant traffic_splits must sum to 100. Current sum: {total}.'
            )
        return variants

    def create(self, validated_data):
        from django.db import transaction
        variants_data = validated_data.pop('variants')

        with transaction.atomic():
            test = ABTest.objects.create(**validated_data)
            for v_data in variants_data:
                ABTestVariant.objects.create(test=test, **v_data)

        return test


class ABTestResultSerializer(serializers.ModelSerializer):
    """Read serializer for detailed test results + statistical analysis."""
    variants              = ABTestVariantSerializer(many=True, read_only=True)
    winner_variant        = ABTestVariantSerializer(read_only=True)
    is_statistically_significant = serializers.SerializerMethodField()
    control_variant       = serializers.SerializerMethodField()
    best_variant          = serializers.SerializerMethodField()
    revenue_uplift_pct    = serializers.SerializerMethodField()

    class Meta:
        model  = ABTest
        fields = [
            'id', 'test_id', 'name', 'test_type', 'status',
            'start_date', 'end_date', 'concluded_at',
            'confidence_level', 'confidence_achieved',
            'statistical_significance', 'is_statistically_significant',
            'winner_variant', 'winner_reason',
            'control_variant', 'best_variant', 'revenue_uplift_pct',
            'variants',
        ]

    def get_is_statistically_significant(self, obj):
        if obj.confidence_achieved and obj.confidence_level:
            return obj.confidence_achieved >= obj.confidence_level
        return False

    def get_control_variant(self, obj):
        ctrl = obj.variants.filter(is_control=True).first()
        return ABTestVariantSerializer(ctrl).data if ctrl else None

    def get_best_variant(self, obj):
        best = obj.variants.order_by('-ecpm').first()
        return ABTestVariantSerializer(best).data if best else None

    def get_revenue_uplift_pct(self, obj):
        control   = obj.variants.filter(is_control=True).first()
        treatment = obj.variants.filter(is_control=False).order_by('-ecpm').first()
        if control and treatment and float(control.ecpm) > 0:
            uplift = ((float(treatment.ecpm) - float(control.ecpm)) / float(control.ecpm)) * 100
            return round(uplift, 2)
        return None
