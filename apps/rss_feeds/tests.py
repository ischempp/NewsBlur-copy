import redis
from utils import json_functions as json
from django.contrib.sites.models import Site
from django.test.client import Client
from django.test import TransactionTestCase
from django.core import management
from django.urls import reverse
from django.conf import settings
from apps.rss_feeds.models import Feed, MStory
from apps.rss_feeds.factories import FeedFactory
from apps.reader.factories import UserSubscriptionFactory, UserSubscriptionFoldersFactory
from apps.profile.factories import UserFactory
from mongoengine.connection import connect, disconnect

NEWSBLUR_DIR = settings.NEWSBLUR_DIR


class TestFeed(TransactionTestCase):
    def setUp(self):
        disconnect()
        mongo_db = settings.MONGO_DB
        connect(**mongo_db)

        site = Site.objects.get_current()
        site.domain = 'testserver'
        site.save()

        settings.REDIS_STORY_HASH_POOL = redis.ConnectionPool(
            host=settings.REDIS_STORY['host'], port=6579, db=10
        )
        settings.REDIS_FEED_READ_POOL = redis.ConnectionPool(
            host=settings.REDIS_SESSIONS['host'], port=6579, db=10
        )
        self.user = UserFactory(username='conesus', password='test')
        self.client = Client()

    def tearDown(self):
        settings.MONGODB.drop_database('test_newsblur')
        r = redis.Redis(connection_pool=settings.REDIS_STORY_HASH_POOL)
        r.flushall()

    def test_load_feeds__gawker(self):
        self.client.login(username='conesus', password='test')
        FeedFactory(pk=10, feed_address=f'{NEWSBLUR_DIR}/apps/rss_feeds/fixtures/gawker1.xml')
        feed = Feed.objects.first()

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 0)

        feed.update(force=True)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 38)

        FeedFactory(pk=1, feed_address=f'{NEWSBLUR_DIR}/apps/rss_feeds/fixtures/gawker2.xml')

        feed.update(force=True)

        # Test: 1 changed char in content
        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 38)

        url = reverse('load-single-feed', kwargs=dict(feed_id=10))
        response = self.client.get(url)
        feed = json.decode(response.content)
        self.assertEqual(len(feed['stories']), 6)

    def test_load_feeds__gothamist(self):
        self.client.login(username='conesus', password='test')
        FeedFactory(
            pk=4,
            feed_address=f'{NEWSBLUR_DIR}/apps/rss_feeds/fixtures/gothamist_aug_2009_1.xml',
            feed_link='http://gothamist.com',
        )

        feed = Feed.objects.get(feed_link__contains='gothamist')
        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 0)

        feed.update(force=True)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 42)

        url = reverse('load-single-feed', kwargs=dict(feed_id=4))
        response = self.client.get(url)
        content = json.decode(response.content)
        self.assertEqual(len(content['stories']), 6)

        FeedFactory(
            pk=4,
            feed_address=f'{NEWSBLUR_DIR}/apps/rss_feeds/fixtures/gothamist_aug_2009_2.xml',
            feed_link='http://gothamist.com',
        )
        feed.update(force=True)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 42)

        url = reverse('load-single-feed', kwargs=dict(feed_id=4))
        response = self.client.get(url)
        # print [c['story_title'] for c in json.decode(response.content)]
        content = json.decode(response.content)
        # Test: 1 changed char in title
        self.assertEqual(len(content['stories']), 6)

    def test_load_feeds__slashdot(self):
        self.client.force_login(self.user)

        old_story_guid = "tag:google.com,2005:reader/item/4528442633bc7b2b"

        feed = FeedFactory(
            pk=5,
            feed_address=f'{NEWSBLUR_DIR}/apps/rss_feeds/fixtures/slashdot1.xml',
            feed_link='/apps/rss_feeds/fixtures/slashdot1.html',
            feed_title='Slashdot',
            last_update="2011-08-27 02:45:21",
        )
        UserSubscriptionFoldersFactory(user=self.user, folders=f"[{feed.pk}]")
        UserSubscriptionFactory(feed=feed, user=self.user, active=True, needs_unread_recalc=True)

        feed = Feed.objects.get(feed_link__contains='slashdot')
        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 0)
        management.call_command('refresh_feed', force=1, feed=feed.id, daemonize=False, skip_checks=False)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 38)

        response = self.client.get(reverse('load-feeds'))
        content = json.decode(response.content)
        self.assertEqual(content['feeds']['5']['nt'], 38)

        self.client.post(reverse('mark-story-as-read'), {'story_id': old_story_guid, 'feed_id': 5})

        response = self.client.get(reverse('refresh-feeds'))
        content = json.decode(response.content)
        self.assertEqual(content['feeds']['5']['nt'], 37)

        FeedFactory(
            pk=5,
            feed_address=f'{NEWSBLUR_DIR}/apps/rss_feeds/fixtures/slashdot2.xml',
            feed_link='/apps/rss_feeds/fixtures/slashdot1.html',
            feed_title='Slashdot',
            last_update="2011-08-27 02:45:21",
        )

        management.call_command('refresh_feed', force=1, feed=5, daemonize=False, skip_checks=False)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 38)

        url = reverse('load-single-feed', kwargs=dict(feed_id=5))
        response = self.client.get(url)

        # pprint([c['story_title'] for c in json.decode(response.content)])
        feed = json.decode(response.content)

        # Test: 1 changed char in title
        self.assertEqual(len(feed['stories']), 6)

        response = self.client.get(reverse('refresh-feeds'))
        content = json.decode(response.content)
        self.assertEqual(content['feeds']['5']['nt'], 37)

    def test_load_feeds__motherjones(self):
        self.client.force_login(self.user)

        management.call_command('loaddata', 'motherjones1.json', verbosity=0, skip_checks=False)

        feed = Feed.objects.get(feed_link__contains='motherjones')

        UserSubscriptionFoldersFactory(user=self.user, folders=f"[{feed.pk}]")
        UserSubscriptionFactory(feed=feed, user=self.user, needs_unread_recalc=True, active=True)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 0)

        management.call_command('refresh_feed', force=1, feed=feed.pk, daemonize=False, skip_checks=False)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 10)

        response = self.client.get(reverse('load-feeds'))
        content = json.decode(response.content)
        self.assertEqual(content['feeds'][str(feed.pk)]['nt'], 10)

        response = self.client.post(
            reverse('mark-story-as-read'), {'story_id': stories[0].story_guid, 'feed_id': feed.pk}
        )

        response = self.client.get(reverse('refresh-feeds'))
        content = json.decode(response.content)
        self.assertEqual(content['feeds'][str(feed.pk)]['nt'], 9)

        management.call_command('loaddata', 'motherjones2.json', verbosity=0, skip_checks=False)
        management.call_command('refresh_feed', force=1, feed=feed.pk, daemonize=False, skip_checks=False)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 10)

        url = reverse('load-single-feed', kwargs=dict(feed_id=feed.pk))
        response = self.client.get(url)

        # pprint([c['story_title'] for c in json.decode(response.content)])
        feed = json.decode(response.content)

        # Test: 1 changed char in title
        self.assertEqual(len(feed['stories']), 6)

        response = self.client.get(reverse('refresh-feeds'))
        content = json.decode(response.content)
        self.assertEqual(content['feeds'][str(feed['feed_id'])]['nt'], 9)

    def test_load_feeds__google(self):
        # Freezegun the date to 2017-04-30

        self.client.force_login(self.user)
        old_story_guid = "blog.google:443/topics/inside-google/google-earths-incredible-3d-imagery-explained/"
        management.call_command('loaddata', 'google1.json', verbosity=1, skip_checks=False)
        feed = Feed.objects.get(pk=766)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 0)

        UserSubscriptionFoldersFactory(user=self.user, folders="[766]")
        UserSubscriptionFactory(feed=feed, user=self.user, needs_unread_recalc=True)

        management.call_command('refresh_feed', force=False, feed=766, daemonize=False, skip_checks=False)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 20)

        response = self.client.get(reverse('load-feeds') + "?update_counts=true")
        content = json.decode(response.content)
        self.assertEqual(content['feeds']['766']['nt'], 20)

        old_story = MStory.objects.get(story_feed_id=feed.pk, story_guid__contains=old_story_guid)
        response = self.client.post(
            reverse('mark-story-hashes-as-read'), {'story_hash': old_story.story_hash}
        )

        response = self.client.get(reverse('load-feeds') + "?update_counts=true")

        content = json.decode(response.content)
        self.assertEqual(content['feeds']['766']['nt'], 19)

        management.call_command('loaddata', 'google2.json', verbosity=1, skip_checks=False)
        management.call_command('refresh_feed', force=False, feed=767, daemonize=False, skip_checks=False)

        stories = MStory.objects(story_feed_id=feed.pk)
        self.assertEqual(stories.count(), 20)

        url = reverse('load-single-feed', kwargs=dict(feed_id=767))
        response = self.client.get(url)
        # pprint([c['story_title'] for c in json.decode(response.content)])
        feed = json.decode(response.content)

        # Test: 1 changed char in title
        self.assertEqual(len(feed['stories']), 6)

        response = self.client.get(reverse('load-feeds') + "?update_counts=true")
        content = json.decode(response.content)
        self.assertEqual(content['feeds']['766']['nt'], 19)

    def test_load_feeds__brokelyn__invalid_xml(self):
        BROKELYN_FEED_ID = 16
        self.client.login(username='conesus', password='test')
        management.call_command('loaddata', 'brokelyn.json', verbosity=0)
        self.assertEquals(Feed.objects.get(pk=BROKELYN_FEED_ID).pk, BROKELYN_FEED_ID)
        management.call_command('refresh_feed', force=1, feed=BROKELYN_FEED_ID, daemonize=False)

        management.call_command('loaddata', 'brokelyn.json', verbosity=0, skip_checks=False)
        management.call_command('refresh_feed', force=1, feed=16, daemonize=False, skip_checks=False)

        url = reverse('load-single-feed', kwargs=dict(feed_id=BROKELYN_FEED_ID))
        response = self.client.get(url)

        # pprint([c['story_title'] for c in json.decode(response.content)])
        feed = json.decode(response.content)

        # Test: 1 changed char in title
        self.assertEqual(len(feed['stories']), 6)

    def test_all_feeds(self):
        pass
