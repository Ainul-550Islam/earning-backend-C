from rest_framework import serializers
from ..models import GeoTargeting


class GeoTargetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoTargeting
        fields = ['id', 'mode', 'countries', 'regions', 'cities', 'updated_at']
        read_only_fields = ['id', 'updated_at']

    def validate_countries(self, value):
        for code in value:
            if len(code) != 2:
                raise serializers.ValidationError(
                    f'"{code}" is not a valid ISO 3166-1 alpha-2 country code.'
                )
        return [c.upper() for c in value]
