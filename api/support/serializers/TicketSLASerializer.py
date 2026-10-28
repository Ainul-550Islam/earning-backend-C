from rest_framework import serializers
from api.support.models import TicketSLA
from django.utils import timezone

class TicketSLASerializer(serializers.ModelSerializer):
    is_breached     = serializers.ReadOnlyField()
    fr_overdue_hours = serializers.SerializerMethodField()
    res_overdue_hours = serializers.SerializerMethodField()

    class Meta:
        model  = TicketSLA
        fields = [
            'id','ticket','first_response_due','resolution_due','first_response_at','resolution_at',
            'first_response_breached','resolution_breached','warning_sent','is_breached',
            'fr_overdue_hours','res_overdue_hours','created_at',
        ]

    def get_fr_overdue_hours(self, obj) -> float:
        if obj.first_response_due and not obj.first_response_at:
            diff = (timezone.now() - obj.first_response_due).total_seconds()
            return round(diff/3600, 1) if diff > 0 else 0
        return 0

    def get_res_overdue_hours(self, obj) -> float:
        if obj.resolution_due and not obj.resolution_at:
            diff = (timezone.now() - obj.resolution_due).total_seconds()
            return round(diff/3600, 1) if diff > 0 else 0
        return 0