# kyc/serializers.py  ── WORLD #1 COMPLETE
from rest_framework import serializers
from .models import (
    KYC, KYCVerificationLog, KYCSubmission,
    KYCBlacklist, KYCRiskProfile, KYCOCRResult, KYCFaceMatchResult,
    KYCWebhookEndpoint, KYCWebhookDeliveryLog, KYCExportJob,
    KYCBulkActionLog, KYCAdminNote, KYCRejectionTemplate,
    KYCAnalyticsSnapshot, KYCIPTracker, KYCVerificationStep,
    KYCOTPLog, KYCTenantConfig, KYCAuditTrail, KYCNotificationLog,
    KYCFeatureFlag, KYCDuplicateGroup,
)


# ══════════════════════════════════════════════════════════════
# ORIGINAL SERIALIZERS  (unchanged)
# ══════════════════════════════════════════════════════════════

class KYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYC
        fields = [
            'id','user','full_name','date_of_birth','phone_number',
            'payment_number','payment_method','address_line','city','country',
            'status','is_name_verified','is_phone_verified','is_payment_verified',
            'document_type','document_number','document_front','document_back',
            'selfie_photo','is_face_verified','reviewed_at','rejection_reason',
            'risk_score','is_duplicate','admin_notes','created_at','updated_at',
        ]
        read_only_fields = ['status','reviewed_at','created_at','updated_at','risk_score']


class KYCAdminSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    email    = serializers.SerializerMethodField()

    class Meta:
        model = KYC
        fields = [
            'id','user','username','email','full_name','date_of_birth','phone_number',
            'payment_number','payment_method','address_line','city','country',
            'status','is_name_verified','is_phone_verified','is_payment_verified',
            'document_type','document_number','document_front','document_back',
            'selfie_photo','is_face_verified','reviewed_at','reviewed_by',
            'rejection_reason','admin_notes','risk_score','risk_factors',
            'is_duplicate','created_at','updated_at',
        ]

    def get_username(self, obj): return obj.user.username if obj.user else None
    def get_email(self, obj):    return obj.user.email    if obj.user else None


class KYCVerificationLogSerializer(serializers.ModelSerializer):
    performed_by__username = serializers.SerializerMethodField()

    class Meta:
        model  = KYCVerificationLog
        fields = ['id','action','details','created_at','performed_by__username']

    def get_performed_by__username(self, obj):
        return obj.performed_by.username if obj.performed_by else None


class KYCSubmissionSerializer(serializers.ModelSerializer):
    front_image        = serializers.ImageField(write_only=True, required=False, allow_null=True)
    back_image         = serializers.ImageField(write_only=True, required=False, allow_null=True)
    selfie_with_id_note = serializers.ImageField(write_only=True, required=False, allow_null=True)
    verification_status = serializers.CharField(source="status", read_only=True)

    class Meta:
        model  = KYCSubmission
        fields = [
            'id','user','status','verification_status','verification_progress',
            'document_type','document_number','nid_front','nid_back','selfie_with_note',
            'image_clarity_score','document_matching_score','face_liveness_check',
            'rejection_reason','created_at','updated_at','submitted_at',
            'front_image','back_image','selfie_with_id_note',
        ]
        read_only_fields = [
            'id','user','status','verification_progress','image_clarity_score',
            'document_matching_score','face_liveness_check','created_at','updated_at','submitted_at',
        ]

    def validate(self, attrs):
        doc_type = attrs.get("document_type")
        if not doc_type: raise serializers.ValidationError({"document_type": "Document type is required."})
        document_number = attrs.get("document_number")
        if not document_number: raise serializers.ValidationError({"document_number": "Document number is required."})
        nid_front = attrs.get("nid_front") or attrs.get("front_image")
        nid_back  = attrs.get("nid_back")  or attrs.get("back_image")
        selfie    = attrs.get("selfie_with_note") or attrs.get("selfie_with_id_note")
        if not nid_front: raise serializers.ValidationError({"nid_front": "Front image is required."})
        if not nid_back:  raise serializers.ValidationError({"nid_back": "Back image is required."})
        if not selfie:    raise serializers.ValidationError({"selfie_with_note": "Selfie with ID note is required."})
        return attrs

    def create(self, validated_data):
        front  = validated_data.pop("front_image", None)
        back   = validated_data.pop("back_image", None)
        selfie = validated_data.pop("selfie_with_id_note", None)
        if validated_data.get("nid_front") is None: validated_data["nid_front"] = front
        if validated_data.get("nid_back")  is None: validated_data["nid_back"]  = back
        if validated_data.get("selfie_with_note") is None: validated_data["selfie_with_note"] = selfie
        user = self.context["request"].user
        submission = KYCSubmission.objects.create(user=user, **validated_data)
        submission.set_submitted()
        return submission

    def update(self, instance, validated_data):
        front  = validated_data.pop("front_image", None)
        back   = validated_data.pop("back_image", None)
        selfie = validated_data.pop("selfie_with_id_note", None)
        if validated_data.get("document_type"):   instance.document_type   = validated_data["document_type"]
        if validated_data.get("document_number"): instance.document_number = validated_data["document_number"]
        if front  is not None: instance.nid_front        = front
        if back   is not None: instance.nid_back          = back
        if selfie is not None: instance.selfie_with_note  = selfie
        instance.set_submitted()
        return instance


# ══════════════════════════════════════════════════════════════
# NEW SERIALIZERS — World #1
# ══════════════════════════════════════════════════════════════

class KYCBlacklistSerializer(serializers.ModelSerializer):
    added_by_username = serializers.SerializerMethodField()

    class Meta:
        model  = KYCBlacklist
        fields = ['id','type','value','reason','is_active','added_by','added_by_username','created_at','expires_at']
        read_only_fields = ['id','added_by','created_at']

    def get_added_by_username(self, obj): return obj.added_by.username if obj.added_by else None


class KYCRiskProfileSerializer(serializers.ModelSerializer):
    risk_level_display = serializers.SerializerMethodField()

    class Meta:
        model  = KYCRiskProfile
        fields = [
            'id','kyc','risk_level','risk_level_display','overall_score',
            'name_match_score','face_match_score','document_clarity_score','ocr_confidence_score',
            'duplicate_flag','age_flag','blacklist_flag','vpn_flag','multiple_attempts_flag',
            'factors','computed_at','requires_manual_review','notes',
        ]
        read_only_fields = ['id','computed_at']

    def get_risk_level_display(self, obj):
        colors = {'low':'#4CAF50','medium':'#FF9800','high':'#F44336','critical':'#B71C1C'}
        return {'label': obj.risk_level.upper(), 'color': colors.get(obj.risk_level, '#9E9E9E')}


class KYCOCRResultSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCOCRResult
        fields = [
            'id','kyc','provider','document_side','extracted_name','extracted_dob',
            'extracted_nid','extracted_address','extracted_father_name','extracted_mother_name',
            'confidence','language','processing_time_ms','is_successful','error','created_at',
        ]
        read_only_fields = ['id','created_at']


class KYCFaceMatchResultSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCFaceMatchResult
        fields = [
            'id','kyc','provider','match_confidence','liveness_score',
            'is_matched','is_liveness_pass','face_detected_selfie','face_detected_doc',
            'multiple_faces','spoofing_detected','processing_time_ms','error','created_at',
        ]
        read_only_fields = ['id','created_at']


class KYCWebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCWebhookEndpoint
        fields = ['id','name','url','events','is_active','timeout_sec','retry_count','headers','created_at','updated_at']
        read_only_fields = ['id','created_at','updated_at']
        extra_kwargs = {'secret_key': {'write_only': True}}


class KYCWebhookDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCWebhookDeliveryLog
        fields = ['id','endpoint','event','response_code','is_success','attempt_count','duration_ms','error','sent_at']
        read_only_fields = ['id','sent_at']


class KYCExportJobSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.SerializerMethodField()

    class Meta:
        model  = KYCExportJob
        fields = ['id','format','status','filters','row_count','file','error','started_at','completed_at','created_at','requested_by_username']
        read_only_fields = ['id','status','row_count','file','error','started_at','completed_at','created_at']

    def get_requested_by_username(self, obj): return obj.requested_by.username if obj.requested_by else None


class KYCBulkActionLogSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.SerializerMethodField()

    class Meta:
        model  = KYCBulkActionLog
        fields = ['id','action','total_affected','success_count','failure_count','reason','errors','created_at','performed_by_username']
        read_only_fields = ['id','created_at']

    def get_performed_by_username(self, obj): return obj.performed_by.username if obj.performed_by else None


class KYCAdminNoteSerializer(serializers.ModelSerializer):
    author_username = serializers.SerializerMethodField()

    class Meta:
        model  = KYCAdminNote
        fields = ['id','kyc','note_type','content','is_internal','is_pinned','author_username','created_at','updated_at']
        read_only_fields = ['id','created_at','updated_at','author_username']

    def get_author_username(self, obj): return obj.author.username if obj.author else None


class KYCRejectionTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCRejectionTemplate
        fields = ['id','title','body','category','is_active','usage_count','created_at']
        read_only_fields = ['id','usage_count','created_at']


class KYCAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCAnalyticsSnapshot
        fields = [
            'id','period','period_start','period_end',
            'total_submitted','total_verified','total_rejected','total_pending','total_expired',
            'avg_risk_score','high_risk_count','duplicate_count','avg_processing_hours',
            'verification_rate','rejection_rate','created_at',
        ]
        read_only_fields = ['id','created_at']


class KYCIPTrackerSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCIPTracker
        fields = ['id','user','kyc','ip_address','action','country','city','is_vpn','is_proxy','is_tor','risk_score','created_at']
        read_only_fields = ['id','created_at']


class KYCVerificationStepSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCVerificationStep
        fields = ['id','kyc','step','status','started_at','completed_at','duration_ms','result','error','retry_count','order']
        read_only_fields = ['id']


class KYCOTPLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCOTPLog
        fields = ['id','user','kyc','phone','purpose','is_used','is_verified','attempt_count','sent_at','verified_at','expires_at']
        read_only_fields = ['id','sent_at']
        extra_kwargs = {'otp_hash': {'write_only': True}}


class KYCTenantConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCTenantConfig
        fields = [
            'id','kyc_required','allowed_document_types','min_age',
            'auto_approve_threshold','auto_reject_threshold','kyc_expiry_days',
            'require_selfie','require_face_match','require_ocr','require_phone_verify',
            'max_submissions_per_user','submission_cooldown_hours',
            'notification_enabled','webhook_enabled','extra_config','updated_at',
        ]
        read_only_fields = ['id','updated_at']


class KYCAuditTrailSerializer(serializers.ModelSerializer):
    actor_username = serializers.SerializerMethodField()

    class Meta:
        model  = KYCAuditTrail
        fields = [
            'id','entity_type','entity_id','action','description','severity',
            'before_state','after_state','diff','actor_username','actor_ip',
            'session_id','request_id','created_at',
        ]
        read_only_fields = ['id','created_at']

    def get_actor_username(self, obj): return obj.actor.username if obj.actor else 'system'


class KYCNotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCNotificationLog
        fields = ['id','channel','event_type','title','message','is_sent','is_read','error','sent_at','read_at','created_at']
        read_only_fields = ['id','created_at']


class KYCFeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = KYCFeatureFlag
        fields = ['id','key','is_enabled','value','description','updated_at']
        read_only_fields = ['id','updated_at']


class KYCDuplicateGroupSerializer(serializers.ModelSerializer):
    kyc_count       = serializers.SerializerMethodField()
    resolved_by_username = serializers.SerializerMethodField()

    class Meta:
        model  = KYCDuplicateGroup
        fields = ['id','match_type','match_value','kyc_count','is_resolved','resolution_note','resolved_by_username','resolved_at','created_at']
        read_only_fields = ['id','created_at']

    def get_kyc_count(self, obj):    return obj.kyc_records.count()
    def get_resolved_by_username(self, obj): return obj.resolved_by.username if obj.resolved_by else None
