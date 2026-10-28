# api/support/tests/factories.py  — WORLD #1
"""factory_boy factories for all support models."""
import factory, random
from django.contrib.auth import get_user_model
User = get_user_model()

class UserFactory(factory.django.DjangoModelFactory):
    class Meta: model = User
    username = factory.Sequence(lambda n: f'user_{n}')
    email    = factory.LazyAttribute(lambda o: f'{o.username}@test.com')
    password = factory.PostGenerationMethodCall('set_password', 'pass123')

class SupportTicketFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import SupportTicket
        model = SupportTicket
    user        = factory.SubFactory(UserFactory)
    subject     = factory.Faker('sentence', nb_words=6)
    description = factory.Faker('paragraph')
    category    = factory.LazyFunction(lambda: random.choice(['payment','coins','account','technical','other']))
    priority    = factory.LazyFunction(lambda: random.choice(['low','medium','high','urgent']))
    status      = 'open'

class TicketMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import TicketMessage
        model = TicketMessage
    ticket  = factory.SubFactory(SupportTicketFactory)
    sender  = factory.SubFactory(UserFactory)
    content = factory.Faker('sentence')
    is_agent= False

class FAQFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import FAQ
        model = FAQ
    question = factory.Faker('sentence', nb_words=8)
    answer   = factory.Faker('paragraph')
    category = 'general'
    is_active= True

class SupportAgentFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import SupportAgent
        model = SupportAgent
    user   = factory.SubFactory(UserFactory)
    role   = 'agent'
    is_active = True
    is_available = True
    max_concurrent_tickets = 10

class KBCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import KBCategory
        model = KBCategory
    name = factory.Faker('word')
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(' ','-'))
    is_active = True

class KBArticleFactory(factory.django.DjangoModelFactory):
    class Meta:
        from api.support.models import KBArticle
        model = KBArticle
    title    = factory.Faker('sentence', nb_words=6)
    slug     = factory.Sequence(lambda n: f'article-{n}')
    body     = factory.Faker('text')
    summary  = factory.Faker('sentence')
    status   = 'published'
    is_public= True
    category = factory.SubFactory(KBCategoryFactory)