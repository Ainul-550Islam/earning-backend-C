"""
DISPUTE_RESOLUTION/dispute_serializers.py — DRF Serializers for Dispute domain
"""
from rest_framework import serializers
from .dispute_model import Dispute, DisputeMessage, DisputeEvidence, DisputeArbitration


class DisputeEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeEvidence
        fields = ["id", "dispute", "uploader", "role", "file", "caption", "created_at"]
        read_only_fields = ["uploader", "dispute", "created_at"]


class DisputeMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = DisputeMessage
        fields = ["id", "dispute", "sender", "sender_username", "role", "body", "is_internal", "created_at"]
        read_only_fields = ["sender", "dispute", "created_at"]


class DisputeArbitrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeArbitration
        fields = "__all__"
        read_only_fields = ["arbitrated_by", "arbitrated_at"]


class DisputeSerializer(serializers.ModelSerializer):
    messages  = DisputeMessageSerializer(many=True, read_only=True)
    evidences = DisputeEvidenceSerializer(many=True, read_only=True)
    raised_by_username = serializers.CharField(source="raised_by.username", read_only=True)

    class Meta:
        model = Dispute
        fields = [
            "id", "tenant", "order", "order_item", "raised_by", "raised_by_username",
            "against_seller", "dispute_type", "status", "description",
            "resolution_note", "created_at", "updated_at", "messages", "evidences",
        ]
        read_only_fields = ["raised_by", "status", "resolution_note", "created_at", "updated_at"]


class DisputeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = ["id", "order", "dispute_type", "status", "created_at"]
