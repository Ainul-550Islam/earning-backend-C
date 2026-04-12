"""
Test Factories — Using factory_boy for all messaging models.
"""
from __future__ import annotations
import uuid
import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user_{n}")
    email    = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    is_active = True


class InternalChatFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.InternalChat"

    name     = ""
    is_group = False
    status   = "ACTIVE"
    created_by = factory.SubFactory(UserFactory)


class GroupChatFactory(InternalChatFactory):
    name     = factory.Sequence(lambda n: f"Group Chat {n}")
    is_group = True


class ChatParticipantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.ChatParticipant"

    chat = factory.SubFactory(InternalChatFactory)
    user = factory.SubFactory(UserFactory)
    role = "MEMBER"


class ChatMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.ChatMessage"

    chat         = factory.SubFactory(InternalChatFactory)
    sender       = factory.SubFactory(UserFactory)
    content      = factory.Sequence(lambda n: f"Test message {n}")
    message_type = "TEXT"
    status       = "SENT"


class AdminBroadcastFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.AdminBroadcast"

    title        = factory.Sequence(lambda n: f"Broadcast {n}")
    body         = "Test broadcast body content."
    status       = "DRAFT"
    audience_type= "ALL_USERS"
    created_by   = factory.SubFactory(UserFactory)


class SupportThreadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.SupportThread"

    user     = factory.SubFactory(UserFactory)
    subject  = factory.Sequence(lambda n: f"Support issue #{n}")
    status   = "OPEN"
    priority = "NORMAL"


class SupportMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.SupportMessage"

    thread        = factory.SubFactory(SupportThreadFactory)
    sender        = factory.SubFactory(UserFactory)
    content       = "Support message content."
    is_agent_reply= False


class UserInboxFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.UserInbox"

    user      = factory.SubFactory(UserFactory)
    item_type = "CHAT_MESSAGE"
    source_id = factory.LazyFunction(uuid.uuid4)
    title     = "Test notification"
    preview   = "Short preview..."
    is_read   = False


class MessageReactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.MessageReaction"

    message = factory.SubFactory(ChatMessageFactory)
    user    = factory.SubFactory(UserFactory)
    emoji   = "👍"


class UserPresenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.UserPresence"
        django_get_or_create = ("user",)

    user         = factory.SubFactory(UserFactory)
    status       = "ONLINE"
    last_seen_at = factory.LazyFunction(timezone.now)
    last_seen_on = "web"


class CallSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.CallSession"

    call_type    = "AUDIO"
    status       = "RINGING"
    initiated_by = factory.SubFactory(UserFactory)
    room_id      = factory.LazyFunction(lambda: uuid.uuid4().hex[:16])


class AnnouncementChannelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.AnnouncementChannel"

    name         = factory.Sequence(lambda n: f"Channel {n}")
    slug         = factory.Sequence(lambda n: f"channel-{n}")
    channel_type = "PUBLIC"
    created_by   = factory.SubFactory(UserFactory)


class DeviceTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.DeviceToken"

    user       = factory.SubFactory(UserFactory)
    token      = factory.LazyFunction(lambda: uuid.uuid4().hex)
    platform   = "android"
    device_name= "Test Device"
    is_active  = True


class UserStoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.UserStory"

    user         = factory.SubFactory(UserFactory)
    story_type   = "text"
    content      = "Test story content"
    is_active    = True
    expires_at   = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=24))
    visibility   = "all"


class BotConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "messaging.BotConfig"

    name              = factory.Sequence(lambda n: f"Bot {n}")
    trigger_type      = "KEYWORD"
    trigger_value     = "hello"
    response_template = "Hello {user_name}! How can I help?"
    is_active         = True
    priority          = 0
