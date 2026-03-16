import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from .models import AuditLog, AuditLogAction, AuditLogLevel, AuditAlertRule, AuditLogConfig

User = get_user_model()

class AuditLogSystemTest(TestCase):
    def setUp(self):
        """টেস্ট ডাটা সেটআপ"""
        self.user = User.objects.create_user(
            username='ainul_dev', 
            password='testpassword123',
            email='ainul@example.com'
        )
        # একটি সাধারণ কনফিগ তৈরি
        self.config = AuditLogConfig.objects.create(
            action=AuditLogAction.LOGIN,
            log_level=AuditLogLevel.INFO,
            retention_days=30
        )

    def test_create_basic_audit_log(self):
        """বেসিক অডিট লগ তৈরি হচ্ছে কি না তা পরীক্ষা"""
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditLogAction.LOGIN,
            level=AuditLogLevel.INFO,
            message="User logged in successfully",
            ip_address="192.168.1.1",
            success=True
        )
        self.assertEqual(log.user.username, 'ainul_dev')
        self.assertEqual(log.action, AuditLogAction.LOGIN)
        self.assertTrue(isinstance(log.id, uuid.UUID))

    def test_json_data_compression_logic(self):
        """অতিরিক্ত বড় ডেটা দিলে তা কম্প্রেস (সারাংশ) হচ্ছে কি না তা পরীক্ষা"""
        # ১০,০০০ ক্যারেক্টারের বেশি বড় একটি বডি তৈরি
        large_body = {"data": "A" * 11000}
        
        log = AuditLog.objects.create(
            action=AuditLogAction.API_CALL,
            message="Testing compression",
            request_body=large_body
        )
        
        # মডেলের save() মেথড অনুযায়ী এটি এখন একটা ছোট ডিকশনারি হওয়ার কথা
        self.assertIn('compressed', log.request_body)
        self.assertEqual(log.request_body['compressed'], True)

    def test_get_changes_method(self):
        """মডেলের get_changes() মেথডটি সঠিক পরিবর্তন দেখাচ্ছে কি না"""
        old_data = {"status": "pending", "amount": 100}
        new_data = {"status": "completed", "amount": 100}
        
        log = AuditLog.objects.create(
            action=AuditLogAction.PROFILE_UPDATE,
            message="Status updated",
            old_data=old_data,
            new_data=new_data
        )
        
        changes = log.get_changes()
        
        # 'status' পরিবর্তন হয়েছে কিন্তু 'amount' হয়নি
        self.assertIn('status', changes)
        self.assertNotIn('amount', changes)
        self.assertEqual(changes['status']['old'], 'pending')
        self.assertEqual(changes['status']['new'], 'completed')

    def test_generic_foreign_key(self):
        """GenericForeignKey ব্যবহার করে অন্য অবজেক্টের সাথে লগ যুক্ত করা"""
        # এখানে আমরা ইউজার মডেলকেই কন্টেন্ট অবজেক্ট হিসেবে টেস্ট করছি
        content_type = ContentType.objects.get_for_model(self.user)
        
        log = AuditLog.objects.create(
            action=AuditLogAction.USER_BAN,
            message=f"Banned user {self.user.username}",
            content_type=content_type,
            object_id=self.user.id
        )
        
        self.assertEqual(log.content_object, self.user)
        self.assertEqual(log.resource_id, str(self.user.id)) # Optional: logic check

    def test_alert_rule_creation(self):
        """অ্যালার্ট রুল মডেল কাজ করছে কি না"""
        rule = AuditAlertRule.objects.create(
            name="Security Alert - Brute Force",
            condition={"attempts__gt": 5},
            action='BLOCK_USER',
            action_config={"duration": "24h"},
            severity=AuditLogLevel.CRITICAL
        )
        self.assertEqual(rule.severity, AuditLogLevel.CRITICAL)
        self.assertTrue(rule.enabled)

    def test_indexing_and_ordering(self):
        """অর্ডারিং (সর্বশেষ লগ আগে) ঠিক আছে কি না"""
        AuditLog.objects.create(action=AuditLogAction.REGISTER, message="First")
        AuditLog.objects.create(action=AuditLogAction.LOGIN, message="Second")
        
        latest_log = AuditLog.objects.first()
        self.assertEqual(latest_log.action, AuditLogAction.LOGIN)