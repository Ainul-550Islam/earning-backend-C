from rest_framework import serializers
from api.support.models import TicketMerge
class TicketMergeSerializer(serializers.ModelSerializer):
    merged_by_username = serializers.CharField(source='merged_by.username', read_only=True)
    class Meta:
        model  = TicketMerge
        fields = ['id','primary_ticket','merged_ticket','merged_by','merged_by_username','merged_at','reason']
        read_only_fields = ['merged_at','merged_by']