from rest_framework import serializers
from api.support.models import TicketTag
class TicketTagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TicketTag
        fields = ['id','name','color','description','created_at']