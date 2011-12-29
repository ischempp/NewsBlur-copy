import datetime
from utils import log as logging
from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
# from django.db import IntegrityError
from apps.rss_feeds.models import Feed, merge_feeds
from apps.rss_feeds.models import MFeedFetchHistory, MPageFetchHistory
from apps.analyzer.models import get_classifiers_for_user
from apps.reader.models import UserSubscription
from utils.user_functions import ajax_login_required
from utils import json_functions as json, feedfinder
from utils.feed_functions import relative_timeuntil, relative_timesince
from utils.user_functions import get_user
from utils.view_functions import get_argument_or_404


@json.json_view
def search_feed(request):
    address = request.REQUEST['address']
    offset = int(request.REQUEST.get('offset', 0))
    feed = Feed.get_feed_from_url(address, create=False, aggressive=True, offset=offset)
    
    if feed:
        return feed.canonical()
    else:
        return dict(code=-1, message="No feed found matching that XML or website address.")
    
@json.json_view
def load_single_feed(request, feed_id):
    user = get_user(request)
    feed = get_object_or_404(Feed, pk=feed_id)
    classifiers = get_classifiers_for_user(user, feed.pk)

    payload = feed.canonical(full=True)
    payload['classifiers'] = classifiers

    return payload
    
@json.json_view
def feed_autocomplete(request):
    query = request.GET.get('term')
    if not query:
        return dict(code=-1, message="Specify a search 'term'.")
        
    feeds = []
    for field in ['feed_address', 'feed_link', 'feed_title']:
        if not feeds:
            feeds = Feed.objects.filter(**{
                '%s__icontains' % field: query,
                'num_subscribers__gt': 1,
                'branch_from_feed__isnull': True,
            }).exclude(
                Q(**{'%s__icontains' % field: 'token'}) |
                Q(**{'%s__icontains' % field: 'private'})
            ).only(
                'feed_title', 
                'feed_address', 
                'num_subscribers'
            ).order_by('-num_subscribers')[:5]
    
    logging.user(request, "~FRAdd Search: ~SB%s ~FG(%s matches)" % (query, len(feeds),))
    
    feeds = [{
        'value': feed.feed_address,
        'label': feed.feed_title,
        'num_subscribers': feed.num_subscribers,
    } for feed in feeds]
    
    return feeds
    
@json.json_view
def load_feed_statistics(request, feed_id):
    stats = dict()
    feed = get_object_or_404(Feed, pk=feed_id)
    feed.save_feed_story_history_statistics()
    feed.save_classifier_counts()
    
    # Dates of last and next update
    stats['last_update'] = relative_timesince(feed.last_update)
    stats['next_update'] = relative_timeuntil(feed.next_scheduled_update)
    
    # Minutes between updates
    update_interval_minutes, random_factor = feed.get_next_scheduled_update(force=True)
    stats['update_interval_minutes'] = update_interval_minutes
    
    # Stories per month - average and month-by-month breakout
    average_stories_per_month, story_count_history = feed.average_stories_per_month, feed.data.story_count_history
    stats['average_stories_per_month'] = average_stories_per_month
    stats['story_count_history'] = story_count_history and json.decode(story_count_history)
    
    # Subscribers
    stats['subscriber_count'] = feed.num_subscribers
    stats['stories_last_month'] = feed.stories_last_month
    stats['last_load_time'] = feed.last_load_time
    stats['premium_subscribers'] = feed.premium_subscribers
    stats['active_subscribers'] = feed.active_subscribers
    
    # Classifier counts
    stats['classifier_counts'] = json.decode(feed.data.feed_classifier_counts)
    
    # Fetch histories
    stats['feed_fetch_history'] = MFeedFetchHistory.feed_history(feed_id)
    stats['page_fetch_history'] = MPageFetchHistory.feed_history(feed_id)
    
    logging.user(request, "~FBStatistics: ~SB%s ~FG(%s/%s/%s subs)" % (feed, feed.num_subscribers, feed.active_subscribers, feed.premium_subscribers,))

    return stats

@json.json_view
def load_feed_settings(request, feed_id):
    stats = dict()
    feed = get_object_or_404(Feed, pk=feed_id)
    
    stats['duplicate_addresses'] = feed.duplicate_addresses.all()
    stats['feed_fetch_history'] = MFeedFetchHistory.feed_history(feed_id)
    stats['page_fetch_history'] = MPageFetchHistory.feed_history(feed_id)
    
    return stats
    
@json.json_view
def exception_retry(request):
    user = get_user(request)
    feed_id = get_argument_or_404(request, 'feed_id')
    reset_fetch = json.decode(request.POST['reset_fetch'])
    feed = get_object_or_404(Feed, pk=feed_id)
    
    feed.next_scheduled_update = datetime.datetime.utcnow()
    feed.has_page_exception = False
    feed.has_feed_exception = False
    feed.active = True
    if reset_fetch:
        logging.user(request, "~FRRefreshing exception feed: ~SB%s" % (feed))
        feed.fetched_once = False
    else:
        logging.user(request, "~FRForcing refreshing feed: ~SB%s" % (feed))
        feed.fetched_once = True
    feed.save()
    
    feed = feed.update(force=True, compute_scores=False, verbose=True)
    usersub = UserSubscription.objects.get(user=user, feed=feed)
    usersub.calculate_feed_scores(silent=False)
    
    feeds = {feed.pk: usersub.canonical(full=True)}
    return {'code': 1, 'feeds': feeds}
    
    
@ajax_login_required
@json.json_view
def exception_change_feed_address(request):
    feed_id = request.POST['feed_id']
    feed = get_object_or_404(Feed, pk=feed_id)
    original_feed = feed
    feed_address = request.POST['feed_address']
    code = -1
    
    if feed.has_page_exception or feed.has_feed_exception:
        # Fix broken feed
        logging.user(request, "~FRFixing feed exception by address: ~SB%s~SN to ~SB%s" % (feed.feed_address, feed_address))
        feed.has_feed_exception = False
        feed.active = True
        feed.fetched_once = False
        feed.feed_address = feed_address
        feed.next_scheduled_update = datetime.datetime.utcnow()
        duplicate_feed = feed.save()
        code = 1
        if duplicate_feed:
            new_feed = Feed.objects.get(pk=duplicate_feed.pk)
            feed = new_feed
            new_feed.next_scheduled_update = datetime.datetime.utcnow()
            new_feed.has_feed_exception = False
            new_feed.active = True
            new_feed.save()
            merge_feeds(new_feed.pk, feed.pk)
    else:
        # Branch good feed
        logging.user(request, "~FRBranching feed by address: ~SB%s~SN to ~SB%s" % (feed.feed_address, feed_address))
        feed, _ = Feed.objects.get_or_create(feed_address=feed_address, feed_link=feed.feed_link)
        if feed.pk != original_feed.pk:
            try:
                feed.branch_from_feed = original_feed.branch_from_feed or original_feed
            except Feed.DoesNotExist:
                feed.branch_from_feed = original_feed
            feed.feed_address_locked = True
            feed.save()
            code = 1

    feed = feed.update()
    feed = Feed.objects.get(pk=feed.pk)

    usersub = UserSubscription.objects.get(user=request.user, feed=original_feed)
    if usersub:
        usersub.switch_feed(feed, original_feed)
    usersub = UserSubscription.objects.get(user=request.user, feed=feed)
        
    usersub.calculate_feed_scores(silent=False)
    
    feed.update_all_statistics()
    classifiers = get_classifiers_for_user(usersub.user, usersub.feed.pk)
    
    feeds = {
        original_feed.pk: usersub.canonical(full=True, classifiers=classifiers), 
    }
    return {
        'code': code, 
        'feeds': feeds, 
        'new_feed_id': usersub.feed.pk,
    }
    
@ajax_login_required
@json.json_view
def exception_change_feed_link(request):
    feed_id = request.POST['feed_id']
    feed = get_object_or_404(Feed, pk=feed_id)
    original_feed = feed
    feed_link = request.POST['feed_link']
    code = -1
    
    if feed.has_page_exception or feed.has_feed_exception:
        # Fix broken feed
        logging.user(request, "~FRFixing feed exception by link: ~SB%s~SN to ~SB%s" % (feed.feed_link, feed_link))
        feed_address = feedfinder.feed(feed_link)
        if feed_address:
            code = 1
            feed.has_page_exception = False
            feed.active = True
            feed.fetched_once = False
            feed.feed_link = feed_link
            feed.feed_address = feed_address
            feed.next_scheduled_update = datetime.datetime.utcnow()
            duplicate_feed = feed.save()
            if duplicate_feed:
                new_feed = Feed.objects.get(pk=duplicate_feed.pk)
                feed = new_feed
                new_feed.next_scheduled_update = datetime.datetime.utcnow()
                new_feed.has_page_exception = False
                new_feed.active = True
                new_feed.save()
    else:
        # Branch good feed
        logging.user(request, "~FRBranching feed by link: ~SB%s~SN to ~SB%s" % (feed.feed_link, feed_link))
        feed, _ = Feed.objects.get_or_create(feed_address=feed.feed_address, feed_link=feed_link)
        if feed.pk != original_feed.pk:
            try:
                feed.branch_from_feed = original_feed.branch_from_feed or original_feed
            except Feed.DoesNotExist:
                feed.branch_from_feed = original_feed
            feed.feed_link_locked = True
            feed.save()
            code = 1

    feed = feed.update()
    feed = Feed.objects.get(pk=feed.pk)

    usersub = UserSubscription.objects.get(user=request.user, feed=original_feed)
    if usersub:
        usersub.switch_feed(feed, original_feed)
    usersub = UserSubscription.objects.get(user=request.user, feed=feed)
        
    usersub.calculate_feed_scores(silent=False)
    
    feed.update_all_statistics()
    classifiers = get_classifiers_for_user(usersub.user, usersub.feed.pk)
    
    feeds = {
        original_feed.pk: usersub.canonical(full=True, classifiers=classifiers), 
    }
    return {
        'code': code, 
        'feeds': feeds, 
        'new_feed_id': usersub.feed.pk,
    }

@login_required
def status(request):
    if not request.user.is_staff:
        logging.user(request, "~SKNON-STAFF VIEWING RSS FEEDS STATUS!")
        assert False
        return HttpResponseForbidden()
    minutes  = int(request.GET.get('minutes', 10))
    now      = datetime.datetime.now()
    hour_ago = now - datetime.timedelta(minutes=minutes)
    feeds    = Feed.objects.filter(last_update__gte=hour_ago).order_by('-last_update')
    return render_to_response('rss_feeds/status.xhtml', {
        'feeds': feeds
    }, context_instance=RequestContext(request))