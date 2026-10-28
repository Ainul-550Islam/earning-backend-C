from rest_framework import serializers
from api.support.models import TicketAttachment
class TicketAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TicketAttachment
        fields = ['id','ticket','message','file','filename','mime_type','size_bytes','size_mb','uploaded_by','created_at']
        read_only_fields = ['created_at','uploaded_by']