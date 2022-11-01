from utils import json_functions as json
from django.contrib.sites.models import Site
from django.test.client import Client
from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from mongoengine.connection import connect, disconnect
from apps.rss_feeds.factories import FeedFactory


class Test_Profile(TestCase):
    """
    fixtures = [
        'subscriptions.json',
        'rss_feeds.json',
    ]
    """

    def setUp(self):
        # disconnect()
        # mongo_db = settings.MONGO_DB
        # conn = connect(**mongo_db)
        site = Site.objects.get_current()
        site.domain = 'testserver'
        site.save()
        site = Site.objects.get_current()
        print(f"\t---> Sites: {site}")

        self.client = Client(HTTP_USER_AGENT='Mozilla/5.0')
        self.feed = FeedFactory()

    def tearDown(self):
        # settings.MONGODB.drop_database('test_newsblur')
        pass

    def test_create_account(self):
        resp = self.client.get(reverse('load-feeds'))
        response = json.decode(resp.content)
        self.assertEquals(response['authenticated'], False)

        response = self.client.post(
            reverse('welcome-signup'),
            {
                'signup-username': 'test',
                'signup-password': 'password',
                'signup-email': 'test@newsblur.com',
            },
        )
        self.assertEquals(response.status_code, 302)

        resp = self.client.get(reverse('load-feeds'))
        response = json.decode(resp.content)
        self.assertEquals(response['authenticated'], True)
