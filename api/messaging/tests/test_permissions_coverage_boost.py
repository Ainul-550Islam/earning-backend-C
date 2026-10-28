"""
test_permissions_coverage_boost.py
====================================
Real-execution coverage for messaging/permissions.py.

Uses RequestFactory to build real request objects and real model
instances wherever the permission class itself issues a DB query
(IsChatParticipant, IsChatAdminOrOwner, IsChannelAdmin). Elsewhere the
permission classes are pure duck-typed attribute checks with no DB
access of their own, so lightweight SimpleNamespace doubles are used to
isolate the permission logic under test - this is not the "deep mocking
that hides bugs" pattern flagged in the audit history, since nothing
belonging to the class under test is mocked away.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from api.messaging.models import CPANotification, ChannelMember, ChatParticipant
from api.messaging.permissions import (
    IsAffiliateOrManager,
    IsChannelAdmin,
    IsChatAdminOrOwner,
    IsChatParticipant,
    IsDeviceOwner,
    IsMediaOwner,
    IsMessageSender,
    IsNotificationRecipient,
    IsStaffOrReadOwn,
    IsSupportAgent,
    IsThreadOwnerOrAgent,
)
from api.messaging.tests.factories import (
    AnnouncementChannelFactory,
    ChatParticipantFactory,
    DeviceTokenFactory,
    InternalChatFactory,
    SupportThreadFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

rf = RequestFactory()


def _request(method="get", user=None):
    builder = getattr(rf, method)
    request = builder("/irrelevant/")
    request.user = user
    return request


# ---------------------------------------------------------------------------
# IsChatParticipant
# ---------------------------------------------------------------------------

class TestIsChatParticipant:
    perm = IsChatParticipant()

    def test_staff_always_allowed(self):
        staff = UserFactory(is_staff=True)
        chat = InternalChatFactory()
        request = _request(user=staff)
        assert self.perm.has_object_permission(request, None, chat) is True

    def test_active_participant_allowed(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        request = _request(user=user)
        assert self.perm.has_object_permission(request, None, chat) is True

    def test_non_participant_denied(self):
        user = UserFactory()
        chat = InternalChatFactory()
        request = _request(user=user)
        assert self.perm.has_object_permission(request, None, chat) is False

    def test_left_participant_denied(self):
        from django.utils import timezone

        user = UserFactory()
        chat = InternalChatFactory()
        participant = ChatParticipantFactory(chat=chat, user=user)
        ChatParticipant.objects.filter(pk=participant.pk).update(
            left_at=timezone.now()
        )
        request = _request(user=user)
        assert self.perm.has_object_permission(request, None, chat) is False


# ---------------------------------------------------------------------------
# IsStaffOrReadOwn
# ---------------------------------------------------------------------------

class TestIsStaffOrReadOwn:
    perm = IsStaffOrReadOwn()

    def test_has_permission_true_for_authenticated(self):
        user = UserFactory()
        assert self.perm.has_permission(_request(user=user), None) is True

    def test_has_permission_false_for_anonymous(self):
        assert self.perm.has_permission(_request(user=AnonymousUser()), None) is False

    def test_object_permission_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        obj = SimpleNamespace(user_id=999)
        assert self.perm.has_object_permission(_request(user=staff), None, obj) is True

    def test_object_permission_owner_allowed(self):
        user = UserFactory()
        obj = SimpleNamespace(user=object(), user_id=user.pk)
        assert self.perm.has_object_permission(_request(user=user), None, obj) is True

    def test_object_permission_non_owner_denied(self):
        user = UserFactory()
        obj = SimpleNamespace(user=object(), user_id=user.pk + 1000)
        assert self.perm.has_object_permission(_request(user=user), None, obj) is False

    def test_object_permission_missing_user_attr_denied(self):
        user = UserFactory()
        obj = SimpleNamespace(other_field=1)
        assert self.perm.has_object_permission(_request(user=user), None, obj) is False


# ---------------------------------------------------------------------------
# IsMessageSender
# ---------------------------------------------------------------------------

class TestIsMessageSender:
    perm = IsMessageSender()

    def test_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        obj = SimpleNamespace(sender=object(), sender_id=999)
        assert self.perm.has_object_permission(_request("post", staff), None, obj) is True

    def test_safe_method_always_allowed(self):
        user = UserFactory()
        obj = SimpleNamespace(sender=object(), sender_id=user.pk + 1)
        assert self.perm.has_object_permission(_request("get", user), None, obj) is True

    def test_sender_can_edit(self):
        user = UserFactory()
        obj = SimpleNamespace(sender=object(), sender_id=user.pk)
        assert self.perm.has_object_permission(_request("patch", user), None, obj) is True

    def test_non_sender_cannot_edit(self):
        user = UserFactory()
        obj = SimpleNamespace(sender=object(), sender_id=user.pk + 1)
        assert self.perm.has_object_permission(_request("delete", user), None, obj) is False


# ---------------------------------------------------------------------------
# IsChatAdminOrOwner
# ---------------------------------------------------------------------------

class TestIsChatAdminOrOwner:
    perm = IsChatAdminOrOwner()

    def test_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        chat = InternalChatFactory()
        assert self.perm.has_object_permission(_request(user=staff), None, chat) is True

    def test_no_participant_record_denied(self):
        user = UserFactory()
        chat = InternalChatFactory()
        assert self.perm.has_object_permission(_request(user=user), None, chat) is False

    def test_member_role_denied(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user, role="MEMBER")
        assert self.perm.has_object_permission(_request(user=user), None, chat) is False

    def test_admin_role_allowed(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user, role="ADMIN")
        assert self.perm.has_object_permission(_request(user=user), None, chat) is True

    def test_owner_role_allowed(self):
        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user, role="OWNER")
        assert self.perm.has_object_permission(_request(user=user), None, chat) is True


# ---------------------------------------------------------------------------
# IsThreadOwnerOrAgent
# ---------------------------------------------------------------------------

class TestIsThreadOwnerOrAgent:
    perm = IsThreadOwnerOrAgent()

    def test_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        thread = SupportThreadFactory()
        assert self.perm.has_object_permission(_request(user=staff), None, thread) is True

    def test_owner_allowed(self):
        user = UserFactory()
        thread = SupportThreadFactory(user=user)
        assert self.perm.has_object_permission(_request(user=user), None, thread) is True

    def test_assigned_agent_allowed(self):
        agent = UserFactory()
        thread = SupportThreadFactory(assigned_agent=agent)
        assert self.perm.has_object_permission(_request(user=agent), None, thread) is True

    def test_unrelated_user_denied(self):
        other = UserFactory()
        thread = SupportThreadFactory()
        assert self.perm.has_object_permission(_request(user=other), None, thread) is False


# ---------------------------------------------------------------------------
# IsAffiliateOrManager
# ---------------------------------------------------------------------------

class TestIsAffiliateOrManager:
    perm = IsAffiliateOrManager()

    def test_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        obj = SimpleNamespace(affiliate_id=1, manager_id=2)
        assert self.perm.has_object_permission(_request(user=staff), None, obj) is True

    def test_affiliate_allowed(self):
        user = UserFactory()
        obj = SimpleNamespace(affiliate_id=user.pk, manager_id=None)
        assert self.perm.has_object_permission(_request(user=user), None, obj) is True

    def test_manager_allowed(self):
        user = UserFactory()
        obj = SimpleNamespace(affiliate_id=None, manager_id=user.pk)
        assert self.perm.has_object_permission(_request(user=user), None, obj) is True

    def test_unrelated_denied(self):
        user = UserFactory()
        obj = SimpleNamespace(affiliate_id=None, manager_id=None)
        assert self.perm.has_object_permission(_request(user=user), None, obj) is False


# ---------------------------------------------------------------------------
# IsNotificationRecipient
# ---------------------------------------------------------------------------

class TestIsNotificationRecipient:
    perm = IsNotificationRecipient()

    def test_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        notif = CPANotification.objects.create(
            recipient=UserFactory(), notification_type="offer.approved",
            title="t", body="b",
        )
        assert self.perm.has_object_permission(_request(user=staff), None, notif) is True

    def test_recipient_allowed(self):
        user = UserFactory()
        notif = CPANotification.objects.create(
            recipient=user, notification_type="offer.approved", title="t", body="b",
        )
        assert self.perm.has_object_permission(_request(user=user), None, notif) is True

    def test_non_recipient_denied(self):
        user = UserFactory()
        notif = CPANotification.objects.create(
            recipient=UserFactory(), notification_type="offer.approved",
            title="t", body="b",
        )
        assert self.perm.has_object_permission(_request(user=user), None, notif) is False


# ---------------------------------------------------------------------------
# IsMediaOwner
# ---------------------------------------------------------------------------

class TestIsMediaOwner:
    perm = IsMediaOwner()

    def test_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        obj = SimpleNamespace(uploaded_by=object(), uploaded_by_id=999)
        assert self.perm.has_object_permission(_request("post", staff), None, obj) is True

    def test_safe_method_allowed(self):
        user = UserFactory()
        obj = SimpleNamespace(uploaded_by=object(), uploaded_by_id=user.pk + 1)
        assert self.perm.has_object_permission(_request("get", user), None, obj) is True

    def test_owner_can_modify(self):
        user = UserFactory()
        obj = SimpleNamespace(uploaded_by=object(), uploaded_by_id=user.pk)
        assert self.perm.has_object_permission(_request("delete", user), None, obj) is True

    def test_non_owner_cannot_modify(self):
        user = UserFactory()
        obj = SimpleNamespace(uploaded_by=object(), uploaded_by_id=user.pk + 1)
        assert self.perm.has_object_permission(_request("delete", user), None, obj) is False


# ---------------------------------------------------------------------------
# IsChannelAdmin
# ---------------------------------------------------------------------------

class TestIsChannelAdmin:
    perm = IsChannelAdmin()

    def test_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        channel = AnnouncementChannelFactory()
        assert self.perm.has_object_permission(_request("post", staff), None, channel) is True

    def test_safe_method_allowed_for_anyone(self):
        user = UserFactory()
        channel = AnnouncementChannelFactory()
        assert self.perm.has_object_permission(_request("get", user), None, channel) is True

    def test_channel_admin_member_allowed(self):
        user = UserFactory()
        channel = AnnouncementChannelFactory()
        ChannelMember.objects.create(channel=channel, user=user, is_admin=True)
        assert self.perm.has_object_permission(_request("post", user), None, channel) is True

    def test_non_admin_member_denied(self):
        user = UserFactory()
        channel = AnnouncementChannelFactory()
        ChannelMember.objects.create(channel=channel, user=user, is_admin=False)
        assert self.perm.has_object_permission(_request("post", user), None, channel) is False

    def test_non_member_denied(self):
        user = UserFactory()
        channel = AnnouncementChannelFactory()
        assert self.perm.has_object_permission(_request("post", user), None, channel) is False


# ---------------------------------------------------------------------------
# IsSupportAgent
# ---------------------------------------------------------------------------

class TestIsSupportAgent:
    perm = IsSupportAgent()

    def test_staff_authenticated_allowed(self):
        staff = UserFactory(is_staff=True)
        assert self.perm.has_permission(_request(user=staff), None) is True

    def test_non_staff_denied(self):
        user = UserFactory()
        assert self.perm.has_permission(_request(user=user), None) is False

    def test_anonymous_denied(self):
        assert self.perm.has_permission(_request(user=AnonymousUser()), None) is False


# ---------------------------------------------------------------------------
# IsDeviceOwner
# ---------------------------------------------------------------------------

class TestIsDeviceOwner:
    perm = IsDeviceOwner()

    def test_staff_bypass(self):
        staff = UserFactory(is_staff=True)
        device = DeviceTokenFactory()
        assert self.perm.has_object_permission(_request(user=staff), None, device) is True

    def test_owner_allowed(self):
        user = UserFactory()
        device = DeviceTokenFactory(user=user)
        assert self.perm.has_object_permission(_request(user=user), None, device) is True

    def test_non_owner_denied(self):
        user = UserFactory()
        device = DeviceTokenFactory()
        assert self.perm.has_object_permission(_request(user=user), None, device) is False
