"""
Messaging Test Factories — factory_boy factories.
"""
from __future__ import annotations
import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from .choices import (
    ChatStatus, MessageType, MessageStatus,
    BroadcastStatus, BroadcastAudienceType,
    SupportThreadStatus, SupportThreadPriority,
    InboxItemType, ParticipantRole,
)
from .models import (
    InternalChat, ChatParticipant, ChatMessage,
    AdminBroadcast, SupportThread, SupportMessage, UserInbox,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"msguser_{n:04d}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpass123!")
        obj = super()._create(model_class, *args, **kwargs)
        obj.set_password(password)
        obj.save()
        return obj


class StaffUserFactory(UserFactory):
    is_staff = True


class InternalChatFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InternalChat

    name = ""
    is_group = False
    status = ChatStatus.ACTIVE
    created_by = factory.SubFactory(UserFactory)
    last_message_at = None
    metadata = factory.LazyFunction(dict)


class GroupChatFactory(InternalChatFactory):
    name = factory.Sequence(lambda n: f"Group {n:04d}")
    is_group = True


class ChatParticipantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ChatParticipant

    chat = factory.SubFactory(InternalChatFactory)
    user = factory.SubFactory(UserFactory)
    role = ParticipantRole.MEMBER
    is_muted = False
    joined_at = factory.LazyFunction(timezone.now)


class ChatMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ChatMessage

    chat = factory.SubFactory(InternalChatFactory)
    sender = factory.SubFactory(UserFactory)
    content = factory.Faker("sentence")
    message_type = MessageType.TEXT
    status = MessageStatus.SENT
    attachments = factory.LazyFunction(list)
    metadata = factory.LazyFunction(dict)


class AdminBroadcastFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AdminBroadcast

    title = factory.Sequence(lambda n: f"Broadcast {n:04d}")
    body = factory.Faker("paragraph")
    status = BroadcastStatus.DRAFT
    audience_type = BroadcastAudienceType.ALL_USERS
    audience_filter = factory.LazyFunction(dict)
    scheduled_at = None
    recipient_count = 0
    delivered_count = 0
    created_by = factory.SubFactory(StaffUserFactory)
    metadata = factory.LazyFunction(dict)


class SupportThreadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SupportThread

    user = factory.SubFactory(UserFactory)
    assigned_agent = None
    subject = factory.Faker("sentence")
    status = SupportThreadStatus.OPEN
    priority = SupportThreadPriority.NORMAL
    metadata = factory.LazyFunction(dict)


class SupportMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SupportMessage

    thread = factory.SubFactory(SupportThreadFactory)
    sender = factory.SubFactory(UserFactory)
    content = factory.Faker("paragraph")
    is_agent_reply = False
    attachments = factory.LazyFunction(list)


class UserInboxFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserInbox

    user = factory.SubFactory(UserFactory)
    item_type = InboxItemType.CHAT_MESSAGE
    source_id = factory.LazyFunction(__import__("uuid").uuid4)
    title = factory.Faker("sentence")
    preview = factory.Faker("sentence")
    is_read = False
    is_archived = False
    metadata = factory.LazyFunction(dict)
