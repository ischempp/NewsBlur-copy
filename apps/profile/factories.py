import factory
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
from apps.profile.models import Profile

import logging

logger = logging.getLogger('faker.factory')
logger.setLevel('DEBUG')


class UserFactory(DjangoModelFactory):
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    username = factory.Faker('email')
    date_joined = factory.Faker('date_time')

    class Meta:
        model = User
