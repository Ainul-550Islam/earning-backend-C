# api/support/factories.py
import factory
import factory.fuzzy
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    username = factory.Sequence(lambda n: f'user_{n}')
    email    = factory.LazyAttribute(lambda o: f'{o.username}@test.com')
    password = factory.PostGenerationMethodCall('set_password', 'pass123')
    is_active = True


class SupportTicketFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import SupportTicket
        model = SupportTicket
    user        = factory.SubFactory(UserFactory)
    subject     = factory.Faker('sentence', nb_words=6)
    description = factory.Faker('paragraph')
    category    = factory.fuzzy.FuzzyChoice(['payment','coins','account','technical','other'])
    priority    = factory.fuzzy.FuzzyChoice(['low','medium','high','urgent'])
    status      = 'open'
    channel     = 'web'


class TicketMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import TicketMessage
        model = TicketMessage
    ticket   = factory.SubFactory(SupportTicketFactory)
    sender   = factory.SubFactory(UserFactory)
    content  = factory.Faker('sentence')
    is_agent = False


class FAQFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import FAQ
        model = FAQ
    question  = factory.Faker('sentence', nb_words=8)
    answer    = factory.Faker('paragraph')
    category  = 'general'
    is_active = True
    order     = factory.Sequence(lambda n: n)


class SupportAgentFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import SupportAgent
        model = SupportAgent
    user         = factory.SubFactory(UserFactory)
    role         = 'agent'
    is_active    = True
    is_available = True


class OfferDisputeFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import OfferDispute
        model = OfferDispute
    user            = factory.SubFactory(UserFactory)
    offer_id        = factory.Sequence(lambda n: f'OFF_{n:04d}')
    expected_amount = factory.fuzzy.FuzzyDecimal(10, 500)
    status          = 'pending'


class KBCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import KBCategory
        model = KBCategory
    name      = factory.Faker('word')
    slug      = factory.Sequence(lambda n: f'category-{n}')
    is_active = True


class KBArticleFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import KBArticle
        model = KBArticle
    title    = factory.Faker('sentence', nb_words=6)
    slug     = factory.Sequence(lambda n: f'article-{n}')
    body     = factory.Faker('text')
    status   = 'published'
    is_public= True
    category = factory.SubFactory(KBCategoryFactory)


class ChatSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import ChatSession
        model = ChatSession
    user   = factory.SubFactory(UserFactory)
    status = 'active'