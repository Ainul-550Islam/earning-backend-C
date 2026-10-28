from rest_framework import serializers
from django.utils import timezone
from api.support.models import SupportTicket, TicketMessage, TicketAttachment


class TicketMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model  = TicketMessage
        fields = ['id','content','is_agent','is_internal','is_read','sender_username','time_ago','created_at','is_edited']

    def get_time_ago(self, obj) -> str:
        diff = (timezone.now() - obj.created_at).total_seconds()
        if diff < 60:    return 'just now'
        if diff < 3600:  return f'{int(diff/60)}m ago'
        if diff < 86400: return f'{int(diff/3600)}h ago'
        return obj.created_at.strftime('%d %b %Y')


class TicketAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TicketAttachment
        fields = ['id','filename','mime_type','size_mb','created_at']


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SupportTicket
        fields = ['subject','category','description','priority','screenshot']

    def validate_subject(self, v):
        if len(v.strip()) < 5:
            raise serializers.ValidationError('Subject must be at least 5 characters.')
        return v.strip()

    def validate_description(self, v):
        if len(v.strip()) < 10:
            raise serializers.ValidationError('Description must be at least 10 characters.')
        return v.strip()


class SupportTicketListSerializer(serializers.ModelSerializer):
    username     = serializers.CharField(source='user.username', read_only=True)
    status_label = serializers.SerializerMethodField()
    wait_hours   = serializers.SerializerMethodField()
    assigned_agent = serializers.SerializerMethodField()
    sla_status   = serializers.SerializerMethodField()

    class Meta:
        model  = SupportTicket
        fields = [
            'id','ticket_id','username','subject','category','priority','status',
            'status_label','channel','created_at','updated_at','wait_hours',
            'satisfaction_rating','message_count','escalated','assigned_agent','sla_status',
        ]

    def get_status_label(self, obj) -> str:
        return {'open':'🟡 Open','in_progress':'🔵 In Progress','waiting_user':'🟠 Waiting','resolved':'✅ Resolved','closed':'⛔ Closed','spam':'🚫 Spam'}.get(obj.status, obj.status)

    def get_wait_hours(self, obj) -> float:
        return round((timezone.now() - obj.created_at).total_seconds()/3600, 1)

    def get_assigned_agent(self, obj) -> str | None:
        return obj.assigned_to.username if obj.assigned_to else None

    def get_sla_status(self, obj) -> dict:
        try:
            sla = obj.sla
            return {'breached': sla.is_breached, 'fr_due': sla.first_response_due, 'res_due': sla.resolution_due}
        except Exception:
            return {}


class SupportTicketSerializer(serializers.ModelSerializer):
    username       = serializers.CharField(source='user.username', read_only=True)
    messages       = serializers.SerializerMethodField()
    attachments    = TicketAttachmentSerializer(many=True, read_only=True)
    assigned_agent = serializers.SerializerMethodField()
    sla_info       = serializers.SerializerMethodField()
    tags           = serializers.SerializerMethodField()

    class Meta:
        model  = SupportTicket
        fields = [
            'id','ticket_id','user','username','subject','category','priority','status',
            'description','screenshot','channel','admin_response','admin_responded_at',
            'created_at','updated_at','resolved_at','escalated','satisfaction_rating',
            'rating_comment','message_count','messages','attachments','assigned_agent','sla_info','tags',
        ]
        read_only_fields = ['user','ticket_id','created_at','updated_at','admin_responded_at','resolved_at']

    def get_messages(self, obj):
        request = self.context.get('request')
        is_agent = request and (request.user.is_staff or request.user.is_superuser)
        qs = obj.messages.filter(is_internal=False) if not is_agent else obj.messages.all()
        return TicketMessageSerializer(qs, many=True).data

    def get_assigned_agent(self, obj) -> str | None:
        return obj.assigned_to.username if obj.assigned_to else None

    def get_sla_info(self, obj) -> dict:
        try:
            sla = obj.sla
            return {'first_response_due': sla.first_response_due, 'resolution_due': sla.resolution_due,
                    'fr_breached': sla.first_response_breached, 'res_breached': sla.resolution_breached}
        except Exception:
            return {}

    def get_tags(self, obj) -> list:
        return [{'id': t.tag.id, 'name': t.tag.name, 'color': t.tag.color} for t in obj.ticket_tags.all()]