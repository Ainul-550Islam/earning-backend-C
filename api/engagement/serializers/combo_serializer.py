# engagement/serializers/combo_serializer.py
"""
Serializers for Combo, Energy models.
These were missing — combo_status view returns raw dicts; these serializers
enable DRF schema generation, validation, and future ViewSet migration.
"""
from rest_framework import serializers
from ..models.combo import ComboConfig, UserCombo, EnergyConfig, EnergyCost, UserEnergy


class ComboConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ComboConfig
        fields = ["id", "action", "max_combo", "decay_seconds", "multiplier_per_step",
                  "tenant", "is_active"]
        read_only_fields = ["id"]


class UserComboSerializer(serializers.ModelSerializer):
    multiplier = serializers.SerializerMethodField()

    class Meta:
        model  = UserCombo
        fields = ["id", "user", "action", "current_combo", "last_action_at",
                  "expires_at", "multiplier"]
        read_only_fields = ["id", "user", "multiplier"]

    def get_multiplier(self, obj):
        config = ComboConfig.objects.filter(action=obj.action).first()
        if config:
            return 1 + (obj.current_combo * config.multiplier_per_step)
        return 1.0


class EnergyConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EnergyConfig
        fields = ["id", "action", "cost", "tenant"]
        read_only_fields = ["id"]


class EnergyCostSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EnergyCost
        fields = ["id", "action", "cost", "tenant"]
        read_only_fields = ["id"]


class UserEnergySerializer(serializers.ModelSerializer):
    current_energy = serializers.SerializerMethodField()

    class Meta:
        model  = UserEnergy
        fields = ["id", "user", "max_energy", "recharge_rate_per_hour",
                  "last_recharged_at", "current_energy"]
        read_only_fields = ["id", "user", "current_energy"]

    def get_current_energy(self, obj):
        return obj.compute_current()
