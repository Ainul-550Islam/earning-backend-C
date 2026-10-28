from rest_framework import serializers
from api.support.models import SupportSettings

class SupportSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SupportSettings
        fields = [
            'id','telegram_group','telegram_admin','whatsapp_number','whatsapp_group',
            'facebook_page','email_support','support_hours_start','support_hours_end',
            'support_timezone','is_support_online','maintenance_mode','maintenance_message',
            'force_update','latest_version_code','latest_version_name','update_message',
            'play_store_url','chat_widget_enabled','chat_widget_color','chat_bot_enabled',
        ]