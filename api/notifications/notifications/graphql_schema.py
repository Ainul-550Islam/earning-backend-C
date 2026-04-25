# earning_backend/api/notifications/graphql_schema.py
"""
GraphQL Schema — GraphQL API for the notification system.

Requires: pip install graphene-django

Add to settings.py:
    INSTALLED_APPS += ['graphene_django']
    GRAPHENE = {'SCHEMA': 'api.notifications.graphql_schema.schema'}

Add to urls.py:
    from graphene_django.views import GraphQLView
    path('graphql/', GraphQLView.as_view(graphiql=True)),
"""
import logging
logger = logging.getLogger(__name__)

try:
    import graphene
    from graphene_django import DjangoObjectType

    class NotificationType(DjangoObjectType):
        class Meta:
            from api.notifications.models import Notification
            model = Notification
            fields = ('id','title','message','notification_type','channel',
                      'priority','is_read','is_sent','created_at','read_at')

    class NotificationTemplateType(DjangoObjectType):
        class Meta:
            from api.notifications.models import NotificationTemplate
            model = NotificationTemplate
            fields = ('id','name','title_en','title_bn','message_en','message_bn',
                      'notification_type','channel','is_active')

    class Query(graphene.ObjectType):
        notifications = graphene.List(
            NotificationType,
            is_read=graphene.Boolean(),
            channel=graphene.String(),
            limit=graphene.Int(default_value=20),
        )
        notification = graphene.Field(NotificationType, id=graphene.ID(required=True))
        unread_count = graphene.Int()
        templates = graphene.List(NotificationTemplateType)

        def resolve_notifications(self, info, is_read=None, channel=None, limit=20):
            from api.notifications.models import Notification
            user = info.context.user
            if not user.is_authenticated:
                return []
            qs = Notification.objects.filter(user=user, is_deleted=False)
            if is_read is not None:
                qs = qs.filter(is_read=is_read)
            if channel:
                qs = qs.filter(channel=channel)
            return qs.order_by('-created_at')[:limit]

        def resolve_notification(self, info, id):
            from api.notifications.models import Notification
            user = info.context.user
            if not user.is_authenticated:
                return None
            return Notification.objects.filter(pk=id, user=user, is_deleted=False).first()

        def resolve_unread_count(self, info):
            from api.notifications.selectors import notification_unread_count
            user = info.context.user
            if not user.is_authenticated:
                return 0
            return notification_unread_count(user=user)

        def resolve_templates(self, info):
            from api.notifications.models import NotificationTemplate
            return NotificationTemplate.objects.filter(is_active=True, is_public=True)

    class MarkNotificationRead(graphene.Mutation):
        class Arguments:
            notification_id = graphene.ID(required=True)

        success = graphene.Boolean()
        notification = graphene.Field(NotificationType)

        def mutate(self, info, notification_id):
            from api.notifications.use_cases import MarkNotificationReadUseCase
            user = info.context.user
            result = MarkNotificationReadUseCase().execute(user=user, notification_id=int(notification_id))
            return MarkNotificationRead(success=result.success)

    class Mutation(graphene.ObjectType):
        mark_notification_read = MarkNotificationRead.Field()

    schema = graphene.Schema(query=Query, mutation=Mutation)
    GRAPHQL_AVAILABLE = True
    logger.info('GraphQL schema initialized successfully')

except ImportError:
    schema = None
    GRAPHQL_AVAILABLE = False
    logger.info('graphql_schema.py: graphene-django not installed. Run: pip install graphene-django')

except Exception as exc:
    schema = None
    GRAPHQL_AVAILABLE = False
    logger.warning(f'graphql_schema.py: {exc}')
