from celery.task import Task
from utils import log as logging
from django.conf import settings

class UpdateFeeds(Task):
    name = 'update-feeds'
    max_retries = 0
    ignore_result = True

    def run(self, feed_pks, **kwargs):
        from apps.rss_feeds.models import Feed
        from apps.statistics.models import MStatistics
        
        options = {
            'fake': bool(MStatistics.get('fake_fetch')),
            'quick': float(MStatistics.get('quick_fetch', 0)),
        }
        
        if not isinstance(feed_pks, list):
            feed_pks = [feed_pks]
            
        for feed_pk in feed_pks:
            try:
                feed = Feed.objects.get(pk=feed_pk)
                feed.update(**options)
            except Feed.DoesNotExist:
                logging.info(" ---> Feed doesn't exist: [%s]" % feed_pk)
            # logging.debug(' Updating: [%s] %s' % (feed_pks, feed))

class NewFeeds(Task):
    name = 'new-feeds'
    max_retries = 0
    ignore_result = True

    def run(self, feed_pks, **kwargs):
        from apps.rss_feeds.models import Feed
        if not isinstance(feed_pks, list):
            feed_pks = [feed_pks]
        
        options = {
            'force': True,
        }
        for feed_pk in feed_pks:
            feed = Feed.objects.get(pk=feed_pk)
            feed.update(options=options)

class PushFeeds(Task):
    name = 'push-feeds'
    max_retries = 0
    ignore_result = True

    def run(self, feed_id, xml, **kwargs):
        from apps.rss_feeds.models import Feed
        
        options = {
            'feed_xml': xml
        }
        feed = Feed.objects.get(pk=feed_id)
        feed.update(options=options)
