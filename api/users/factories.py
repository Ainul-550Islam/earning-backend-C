import factory
from factory.django import DjangoModelFactory
from .models import User, UserProfile


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'user{n}')