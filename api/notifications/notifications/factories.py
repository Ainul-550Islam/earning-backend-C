# earning_backend/api/notifications/factories.py
"""
Factories — Factory Boy model factories for testing.
Creates realistic test data for all notification models.
"""
import factory
from django.utils import timezone


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        from notifications.models import Notification
        model = Notification

    user = factory.SubFactory('users.factories.UserFactory')
    title = factory.Sequence(lambda n: f'Test Notification {n}')
    message = factory.Faker('sentence', nb_words=12)
    notification_type = 'announcement'
    channel = 'in_app'
    priority = 'medium'
    is_read = False
    is_deleted = False


class UnreadNotificationFactory(NotificationFactory):
    is_read = False


class ReadNotificationFactory(NotificationFactory):
    is_read = True
    read_at = factory.LazyFunction(timezone.now)


class PushNotificationFactory(NotificationFactory):
    channel = 'push'
    priority = 'high'


class EmailNotificationFactory(NotificationFactory):
    channel = 'email'


class UrgentNotificationFactory(NotificationFactory):
    priority = 'urgent'
    notification_type = 'fraud_detected'


class NotificationTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        from notifications.models import NotificationTemplate
        model = NotificationTemplate

    name = factory.Sequence(lambda n: f'template_{n}')
    title_en = factory.Faker('sentence', nb_words=5)
    message_en = factory.Faker('sentence', nb_words=15)
    notification_type = 'announcement'
    channel = 'in_app'
    is_active = True
    is_public = True
    created_by = factory.SubFactory('users.factories.UserFactory')


class DeviceTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        from notifications.models import DeviceToken
        model = DeviceToken

    user = factory.SubFactory('users.factories.UserFactory')
    device_type = 'android'
    fcm_token = factory.Sequence(lambda n: f'fcm_token_{n}_test')
    is_active = True
    push_enabled = True


class InAppMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        from notifications.models.channel import InAppMessage
        model = InAppMessage

    user = factory.SubFactory('users.factories.UserFactory')
    message_type = 'toast'
    title = factory.Faker('sentence', nb_words=5)
    body = factory.Faker('sentence', nb_words=12)
    is_read = False
    is_dismissed = False
    display_priority = 5
