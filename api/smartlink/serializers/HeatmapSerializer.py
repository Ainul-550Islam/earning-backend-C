from rest_framework import serializers
from ..models import ClickHeatmap


class HeatmapSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClickHeatmap
        fields = [
            'id', 'smartlink', 'country', 'date',
            'click_count', 'unique_click_count',
            'conversion_count', 'revenue', 'epc', 'updated_at',
        ]
        read_only_fields = fields
