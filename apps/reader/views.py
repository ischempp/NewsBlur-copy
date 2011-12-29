import datetime
import time
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.template.loader import render_to_string
from django.db import IntegrityError
from django.views.decorators.cache import never_cache
from django.core.urlresolvers import reverse
from django.contrib.auth import login as login_user
from django.contrib.auth import logout as logout_user
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.conf import settings
from django.core.mail import mail_admins
from django.core.validators import email_re
from django.core.mail import EmailMultiAlternatives
from pymongo.helpers import OperationFailure
from collections import defaultdict
from operator import itemgetter
from apps.recommendations.models import RecommendedFeed
from apps.analyzer.models import MClassifierTitle, MClassifierAuthor, MClassifierFeed, MClassifierTag
from apps.analyzer.models import apply_classifier_titles, apply_classifier_feeds, apply_classifier_authors, apply_classifier_tags
from apps.analyzer.models import get_classifiers_for_user
from apps.profile.models import Profile
from apps.reader.models import UserSubscription, UserSubscriptionFolders, MUserStory, Feature
from apps.reader.forms import SignupForm, LoginForm, FeatureForm
from apps.rss_feeds.models import MFeedIcon
from apps.statistics.models import MStatistics, MFeedback
try:
    from apps.rss_feeds.models import Feed, MFeedPage, DuplicateFeed, MStory, MStarredStory, FeedLoadtime
except:
    pass
from utils import json_functions as json
from utils.user_functions import get_user, ajax_login_required
from utils.feed_functions import relative_timesince
from utils.story_functions import format_story_link_date__short
from utils.story_functions import format_story_link_date__long
from utils.story_functions import bunch
from utils.story_functions import story_score
from utils import log as logging
from utils.view_functions import get_argument_or_404
from utils.ratelimit import ratelimit
from vendor.timezones.utilities import localtime_for_timezone

SINGLE_DAY = 60*60*24

@never_cache
def index(request):
    if request.method == "POST":
        if request.POST['submit'] == 'login':
            login_form  = LoginForm(request.POST, prefix='login')
            signup_form = SignupForm(prefix='signup')
        else:
            login_form  = LoginForm(prefix='login')
            signup_form = SignupForm(request.POST, prefix='signup')
    else:
        login_form  = LoginForm(prefix='login')
        signup_form = SignupForm(prefix='signup')
    
    user         = get_user(request)
    authed       = request.user.is_authenticated()
    features     = Feature.objects.all()[:3]
    feature_form = FeatureForm() if request.user.is_staff else None
    feed_count   = UserSubscription.objects.filter(user=request.user).count() if authed else 0
    active_count = UserSubscription.objects.filter(user=request.user, active=True).count() if authed else 0
    train_count  = UserSubscription.objects.filter(user=request.user, active=True, is_trained=False, feed__stories_last_month__gte=1).count() if authed else 0
    recommended_feeds = RecommendedFeed.objects.filter(is_public=True, approved_date__lte=datetime.datetime.now()).select_related('feed')[:2]
    unmoderated_feeds = RecommendedFeed.objects.filter(is_public=False, declined_date__isnull=True).select_related('feed')[:2]
    statistics   = MStatistics.all()
    feedbacks    = MFeedback.all()
    start_import_from_google_reader = request.session.get('import_from_google_reader', False)
    if start_import_from_google_reader:
        del request.session['import_from_google_reader']

    return render_to_response('reader/feeds.xhtml', {
        'user_profile'      : hasattr(user, 'profile') and user.profile,
        'login_form'        : login_form,
        'signup_form'       : signup_form,
        'feature_form'      : feature_form,
        'features'          : features,
        'feed_count'        : feed_count,
        'active_count'      : active_count,
        'train_count'       : active_count - train_count,
        'account_images'    : range(1, 4),
        'recommended_feeds' : recommended_feeds,
        'unmoderated_feeds' : unmoderated_feeds,
        'statistics'        : statistics,
        'feedbacks'         : feedbacks,
        'start_import_from_google_reader': start_import_from_google_reader,
    }, context_instance=RequestContext(request))

@never_cache
def login(request):
    code = -1
    message = ""
    if request.method == "POST":
        form = LoginForm(request.POST, prefix='login')
        if form.is_valid():
            login_user(request, form.get_user())
            if request.POST.get('api'):
                logging.user(form.get_user(), "~FG~BB~SKiPhone Login~FW")
                code = 1
            else:
                logging.user(form.get_user(), "~FG~BBLogin~FW")
                return HttpResponseRedirect(reverse('index'))
        else:
            message = form.errors.items()[0][1][0]

    if request.POST.get('api'):
        return HttpResponse(json.encode(dict(code=code, message=message)), mimetype='application/json')
    else:
        return index(request)
    
@never_cache
def signup(request):
    if request.method == "POST":
        form = SignupForm(prefix='signup', data=request.POST)
        if form.is_valid():
            new_user = form.save()
            login_user(request, new_user)
            logging.user(new_user, "~FG~SB~BBNEW SIGNUP~FW")
            return HttpResponseRedirect(reverse('index'))

    return index(request)
        
@never_cache
def logout(request):
    logging.user(request, "~FG~BBLogout~FW")
    logout_user(request)
    
    if request.GET.get('api'):
        return HttpResponse(json.encode(dict(code=1)), mimetype='application/json')
    else:
        return HttpResponseRedirect(reverse('index'))

def autologin(request, username, secret):
    next = request.GET.get('next', '')
    
    if not username or not secret:
        return HttpResponseForbidden()
    
    profile = Profile.objects.filter(user__username=username, secret_token=secret)
    if not profile:
        return HttpResponseForbidden()

    user = profile[0].user
    user.backend = settings.AUTHENTICATION_BACKENDS[0]
    login_user(request, user)
    logging.user(user, "~FG~BB~SKAuto-Login. Next stop: %s~FW" % (next if next else 'Homepage',))
    
    if next:
        next = '?next=' + next
        
    return HttpResponseRedirect(reverse('index') + next)
    
@ratelimit(minutes=1, requests=12)
@json.json_view
def load_feeds(request):
    user             = get_user(request)
    feeds            = {}
    not_yet_fetched  = False
    include_favicons = request.REQUEST.get('include_favicons', False)
    flat             = request.REQUEST.get('flat', False)
    update_counts    = request.REQUEST.get('update_counts', False)
    
    if include_favicons == 'false': include_favicons = False
    if update_counts == 'false': update_counts = False
    if flat == 'false': flat = False
    
    if flat: return load_feeds_flat(request)
    
    try:
        folders = UserSubscriptionFolders.objects.get(user=user)
    except UserSubscriptionFolders.DoesNotExist:
        data = dict(feeds=[], folders=[])
        return data
    except UserSubscriptionFolders.MultipleObjectsReturned:
        UserSubscriptionFolders.objects.filter(user=user)[1:].delete()
        folders = UserSubscriptionFolders.objects.get(user=user)
    
    user_subs = UserSubscription.objects.select_related('feed').filter(user=user)
    
    for sub in user_subs:
        pk = sub.feed.pk
        if update_counts:
            sub.calculate_feed_scores(silent=True)
        feeds[pk] = sub.canonical(include_favicon=include_favicons)
        if feeds[pk].get('not_yet_fetched'):
            not_yet_fetched = True
        if not sub.feed.active and not sub.feed.has_feed_exception and not sub.feed.has_page_exception:
            sub.feed.count_subscribers()
            sub.feed.schedule_feed_fetch_immediately()
        if sub.active and sub.feed.active_subscribers <= 0:
            sub.feed.count_subscribers()
            sub.feed.schedule_feed_fetch_immediately()
            
    if not_yet_fetched:
        for f in feeds:
            if 'not_yet_fetched' not in feeds[f]:
                feeds[f]['not_yet_fetched'] = False

    starred_count = MStarredStory.objects(user_id=user.pk).count()

    data = {
        'feeds': feeds,
        'folders': json.decode(folders.folders),
        'starred_count': starred_count,
    }
    return data

@json.json_view
def load_feed_favicons(request):
    user = get_user(request)
    feed_ids = request.REQUEST.getlist('feed_ids')
    user_subs = UserSubscription.objects.select_related('feed').filter(user=user, active=True)
    if feed_ids and len(feed_ids) > 0:
        user_subs = user_subs.filter(feed__in=feed_ids)

    feed_ids   = [sub['feed__pk'] for sub in user_subs.values('feed__pk')]
    feed_icons = dict([(i.feed_id, i.data) for i in MFeedIcon.objects(feed_id__in=feed_ids)])
        
    return feed_icons

def load_feeds_flat(request):
    user = request.user
    include_favicons = request.REQUEST.get('include_favicons', False)
    feeds = {}
    iphone_version = "1.2"
    
    if include_favicons == 'false': include_favicons = False
    
    if not user.is_authenticated():
        return HttpResponseForbidden()
    
    try:
        folders = UserSubscriptionFolders.objects.get(user=user)
    except UserSubscriptionFolders.DoesNotExist:
        data = dict(folders=[], iphone_version=iphone_version)
        return data
        
    user_subs = UserSubscription.objects.select_related('feed').filter(user=user, active=True)

    for sub in user_subs:
        if sub.needs_unread_recalc:
            sub.calculate_feed_scores(silent=True)
        feeds[sub.feed.pk] = sub.canonical(include_favicon=include_favicons)
    
    folders = json.decode(folders.folders)
    flat_folders = {}
    
    def make_feeds_folder(items, parent_folder="", depth=0):
        for item in items:
            if isinstance(item, int) and item in feeds:
                if not parent_folder:
                    parent_folder = ' '
                if parent_folder in flat_folders:
                    flat_folders[parent_folder].append(item)
                else:
                    flat_folders[parent_folder] = [item]
            elif isinstance(item, dict):
                for folder_name in item:
                    folder = item[folder_name]
                    flat_folder_name = "%s%s%s" % (
                        parent_folder if parent_folder and parent_folder != ' ' else "",
                        " - " if parent_folder and parent_folder != ' ' else "",
                        folder_name
                    )
                    flat_folders[flat_folder_name] = []
                    make_feeds_folder(folder, flat_folder_name, depth+1)
        
    make_feeds_folder(folders)
    data = dict(flat_folders=flat_folders, feeds=feeds, user=user.username, iphone_version=iphone_version)
    return data

@ratelimit(minutes=1, requests=10)
@json.json_view
def refresh_feeds(request):
    start = datetime.datetime.utcnow()
    user = get_user(request)
    feed_ids = request.REQUEST.getlist('feed_id')
    feeds = {}
    user_subs = UserSubscription.objects.select_related('feed').filter(user=user, active=True)
    feed_ids = [f for f in feed_ids if f and not f.startswith('river')]
    if feed_ids:
        user_subs = user_subs.filter(feed__in=feed_ids)
    UNREAD_CUTOFF = datetime.datetime.utcnow() - datetime.timedelta(days=settings.DAYS_OF_UNREAD)
    favicons_fetching = [int(f) for f in request.REQUEST.getlist('favicons_fetching') if f]
    feed_icons = dict([(i.feed_id, i) for i in MFeedIcon.objects(feed_id__in=favicons_fetching)])

    for i, sub in enumerate(user_subs):
        pk = sub.feed.pk
        if (sub.needs_unread_recalc or 
            sub.unread_count_updated < UNREAD_CUTOFF or 
            sub.oldest_unread_story_date < UNREAD_CUTOFF):
            sub = sub.calculate_feed_scores(silent=True)
        if not sub: continue # TODO: Figure out the correct sub and give it a new feed_id
        feeds[pk] = {
            'ps': sub.unread_count_positive,
            'nt': sub.unread_count_neutral,
            'ng': sub.unread_count_negative,
        }
        if sub.feed.has_feed_exception or sub.feed.has_page_exception:
            feeds[pk]['has_exception'] = True
            feeds[pk]['exception_type'] = 'feed' if sub.feed.has_feed_exception else 'page'
            feeds[pk]['feed_address'] = sub.feed.feed_address
            feeds[pk]['exception_code'] = sub.feed.exception_code
        if request.REQUEST.get('check_fetch_status', False):
            feeds[pk]['not_yet_fetched'] = not sub.feed.fetched_once
            
        if sub.feed.pk in favicons_fetching and sub.feed.pk in feed_icons:
            feeds[pk]['favicon'] = feed_icons[sub.feed.pk].data
            feeds[pk]['favicon_color'] = feed_icons[sub.feed.pk].color
            feeds[pk]['favicon_fetching'] = sub.feed.favicon_fetching
    
    user_subs = UserSubscription.objects.select_related('feed').filter(user=user, active=True)
    
    if favicons_fetching:
        sub_feed_ids = [s.feed.pk for s in user_subs]
        moved_feed_ids = [f for f in favicons_fetching if f not in sub_feed_ids]
        for moved_feed_id in moved_feed_ids:
            duplicate_feeds = DuplicateFeed.objects.filter(duplicate_feed_id=moved_feed_id)
            if duplicate_feeds and duplicate_feeds[0].feed.pk in feeds:
                feeds[moved_feed_id] = feeds[duplicate_feeds[0].feed.pk]
                feeds[moved_feed_id]['dupe_feed_id'] = duplicate_feeds[0].feed.pk
        
    if settings.DEBUG or request.REQUEST.get('check_fetch_status'):
        diff = datetime.datetime.utcnow()-start
        timediff = float("%s.%.2s" % (diff.seconds, (diff.microseconds / 1000)))
        logging.user(request, "~FBRefreshing %s feeds (%s seconds) (%s/%s)" % (user_subs.count(), timediff, request.REQUEST.get('check_fetch_status', False), len(favicons_fetching)))
    
    return {'feeds': feeds}

def refresh_feed(request, feed_id):
    user = get_user(request)
    feed = get_object_or_404(Feed, pk=feed_id)
    
    feed = feed.update(force=True, compute_scores=False)
    usersub = UserSubscription.objects.get(user=user, feed=feed)
    usersub.calculate_feed_scores(silent=False)

    return load_single_feed(request, feed_id)
    
@json.json_view
def load_single_feed(request, feed_id):
    start        = time.time()
    user         = get_user(request)
    offset       = int(request.REQUEST.get('offset', 0))
    limit        = int(request.REQUEST.get('limit', 6))
    page         = int(request.REQUEST.get('page', 1))
    dupe_feed_id = None
    userstories_db = None

    if page: offset = limit * (page-1)
    if not feed_id: raise Http404
        
    try:
        feed = Feed.objects.get(id=feed_id)
    except Feed.DoesNotExist:
        feed_address = request.REQUEST.get('feed_address')
        dupe_feed = DuplicateFeed.objects.filter(duplicate_address=feed_address)
        if dupe_feed:
            feed = dupe_feed[0].feed
            dupe_feed_id = feed_id
        else:
            raise Http404
        
    stories = feed.get_stories(offset, limit) 
        
    # Get intelligence classifier for user
    classifier_feeds   = list(MClassifierFeed.objects(user_id=user.pk, feed_id=feed_id))
    classifier_authors = list(MClassifierAuthor.objects(user_id=user.pk, feed_id=feed_id))
    classifier_titles  = list(MClassifierTitle.objects(user_id=user.pk, feed_id=feed_id))
    classifier_tags    = list(MClassifierTag.objects(user_id=user.pk, feed_id=feed_id))
    
    checkpoint1 = time.time()
    
    usersub = UserSubscription.objects.get(user=user, feed=feed)
    userstories = []
    if usersub and stories:
        story_ids = [story['id'] for story in stories]
        userstories_db = MUserStory.objects(user_id=user.pk,
                                            feed_id=feed.pk,
                                            story_id__in=story_ids).only('story_id')
        starred_stories = MStarredStory.objects(user_id=user.pk, 
                                                story_feed_id=feed_id, 
                                                story_guid__in=story_ids).only('story_guid', 'starred_date')
        starred_stories = dict([(story.story_guid, story.starred_date) for story in starred_stories])
        userstories = set(us.story_id for us in userstories_db)
            
    checkpoint2 = time.time()
    
    for story in stories:
        story_date = localtime_for_timezone(story['story_date'], user.profile.timezone)
        now = localtime_for_timezone(datetime.datetime.now(), user.profile.timezone)
        story['short_parsed_date'] = format_story_link_date__short(story_date, now)
        story['long_parsed_date'] = format_story_link_date__long(story_date, now)
        if usersub:
            if story['id'] in userstories:
                story['read_status'] = 1
            elif not story.get('read_status') and story['story_date'] < usersub.mark_read_date:
                story['read_status'] = 1
            elif not story.get('read_status') and story['story_date'] > usersub.last_read_date:
                story['read_status'] = 0
            if story['id'] in starred_stories:
                story['starred'] = True
                starred_date = localtime_for_timezone(starred_stories[story['id']], user.profile.timezone)
                story['starred_date'] = format_story_link_date__long(starred_date, now)
        else:
            story['read_status'] = 1
        story['intelligence'] = {
            'feed': apply_classifier_feeds(classifier_feeds, feed),
            'author': apply_classifier_authors(classifier_authors, story),
            'tags': apply_classifier_tags(classifier_tags, story),
            'title': apply_classifier_titles(classifier_titles, story),
        }

    checkpoint3 = time.time()
    
    # Intelligence
    feed_tags = json.decode(feed.data.popular_tags) if feed.data.popular_tags else []
    feed_authors = json.decode(feed.data.popular_authors) if feed.data.popular_authors else []
    classifiers = get_classifiers_for_user(user, feed_id, classifier_feeds, 
                                           classifier_authors, classifier_titles, classifier_tags)
    
    if usersub:
        usersub.feed_opens += 1
        usersub.save()
    diff1 = checkpoint1-start
    diff2 = checkpoint2-start
    diff3 = checkpoint3-start
    timediff = time.time()-start
    last_update = relative_timesince(feed.last_update)
    logging.user(request, "~FYLoading feed: ~SB%s%s ~SN(%.4s seconds, ~SB%.4s/%.4s(%s)/%.4s~SN)" % (
        feed.feed_title[:32], ('~SN/p%s' % page) if page > 1 else '', timediff,
        diff1, diff2, userstories_db and userstories_db.count() or '~SN0~SB', diff3))
    FeedLoadtime.objects.create(feed=feed, loadtime=timediff)
    
    data = dict(stories=stories, 
                feed_tags=feed_tags, 
                feed_authors=feed_authors, 
                classifiers=classifiers,
                last_update=last_update,
                feed_id=feed.pk,
                elapsed_time=round(float(timediff), 2))
    
    if dupe_feed_id: data['dupe_feed_id'] = dupe_feed_id
    if not usersub:
        data.update(feed.canonical())
        
    return data

def load_feed_page(request, feed_id):
    if not feed_id:
        raise Http404
        
    data = MFeedPage.get_data(feed_id=feed_id)

    if not data:
        data = "Fetching feed..."
    
    return HttpResponse(data, mimetype='text/html')
    
@json.json_view
def load_starred_stories(request):
    user = get_user(request)
    offset = int(request.REQUEST.get('offset', 0))
    limit = int(request.REQUEST.get('limit', 10))
    page = int(request.REQUEST.get('page', 0))
    if page: offset = limit * (page - 1)
        
    mstories = MStarredStory.objects(user_id=user.pk).order_by('-starred_date')[offset:offset+limit]
    stories = Feed.format_stories(mstories)
    
    for story in stories:
        story_date = localtime_for_timezone(story['story_date'], user.profile.timezone)
        now = localtime_for_timezone(datetime.datetime.now(), user.profile.timezone)
        story['short_parsed_date'] = format_story_link_date__short(story_date, now)
        story['long_parsed_date'] = format_story_link_date__long(story_date, now)
        starred_date = localtime_for_timezone(story['starred_date'], user.profile.timezone)
        story['starred_date'] = format_story_link_date__long(starred_date, now)
        story['read_status'] = 1
        story['starred'] = True
        story['intelligence'] = {
            'feed': 0,
            'author': 0,
            'tags': 0,
            'title': 0,
        }
    
    logging.user(request, "~FCLoading starred stories: ~SB%s stories" % (len(stories)))
    
    return dict(stories=stories)

@json.json_view
def load_river_stories(request):
    limit                = 18
    offset               = int(request.REQUEST.get('offset', 0))
    start                = time.time()
    user                 = get_user(request)
    feed_ids             = [int(feed_id) for feed_id in request.REQUEST.getlist('feeds') if feed_id]
    original_feed_ids    = list(feed_ids)
    page                 = int(request.REQUEST.get('page', 1))
    read_stories_count   = int(request.REQUEST.get('read_stories_count', 0))
    days_to_keep_unreads = datetime.timedelta(days=settings.DAYS_OF_UNREAD)
    
    if not feed_ids: 
        logging.user(request, "~FCLoading empty river stories: page %s" % (page))
        return dict(stories=[])
    
    # Fetch all stories at and before the page number.
    # Not a single page, because reading stories can move them up in the unread order.
    # `read_stories_count` is an optimization, works best when all 25 stories before have been read.
    offset = (page-1) * limit - read_stories_count
    limit = page * limit - read_stories_count
    
    # Read stories to exclude
    read_stories = MUserStory.objects(user_id=user.pk, feed_id__in=feed_ids).only('story_id')
    read_stories = [rs.story_id for rs in read_stories]
    
    # Determine mark_as_read dates for all feeds to ignore all stories before this date.
    feed_counts     = {}
    feed_last_reads = {}
    for feed_id in feed_ids:
        try:
            usersub = UserSubscription.objects.get(feed__pk=feed_id, user=user)
        except UserSubscription.DoesNotExist:
            continue
        if not usersub: continue
        feed_counts[feed_id] = (usersub.unread_count_negative * 1 + 
                                usersub.unread_count_neutral * 10 +
                                usersub.unread_count_positive * 20)
        feed_last_reads[feed_id] = int(time.mktime(usersub.mark_read_date.timetuple()))

    feed_counts = sorted(feed_counts.items(), key=itemgetter(1))[:40]
    feed_ids = [f[0] for f in feed_counts]
    feed_last_reads = dict([(str(feed_id), feed_last_reads[feed_id]) for feed_id in feed_ids
                            if feed_id in feed_last_reads])
    feed_counts = dict(feed_counts)

    # After excluding read stories, all that's left are stories 
    # past the mark_read_date. Everything returned is guaranteed to be unread.
    mstories = MStory.objects(
        story_guid__nin=read_stories,
        story_feed_id__in=feed_ids,
        # story_date__gte=start - days_to_keep_unreads
    ).map_reduce("""function() {
            var d = feed_last_reads[this[~story_feed_id]];
            if (this[~story_date].getTime()/1000 > d) {
                emit(this[~id], this);
            }
        }""",
        """function(key, values) {
            return values[0];
        }""",
        output='inline',
        scope={
            'feed_last_reads': feed_last_reads
        }
    )
    try:
        mstories = [story.value for story in mstories if story and story.value]
    except OperationFailure, e:
        raise e

    mstories = sorted(mstories, cmp=lambda x, y: cmp(story_score(y, days_to_keep_unreads), 
                                                     story_score(x, days_to_keep_unreads)))

    # Prune the river to only include a set number of stories per feed
    # story_feed_counts = defaultdict(int)
    # mstories_pruned = []
    # for story in mstories:
    #     print story['story_title'], story_feed_counts[story['story_feed_id']]
    #     if story_feed_counts[story['story_feed_id']] >= 3: continue
    #     mstories_pruned.append(story)
    #     story_feed_counts[story['story_feed_id']] += 1
    
    stories = []
    for i, story in enumerate(mstories):
        if i < offset: continue
        if i >= limit: break
        stories.append(bunch(story))
    stories = Feed.format_stories(stories)
    found_feed_ids = list(set([story['story_feed_id'] for story in stories]))
    
    # Find starred stories
    try:
        starred_stories = MStarredStory.objects(
            user_id=user.pk,
            story_feed_id__in=found_feed_ids
        ).only('story_guid', 'starred_date')
        starred_stories = dict([(story.story_guid, story.starred_date) 
                                for story in starred_stories])
    except OperationFailure:
        logging.info(" ***> Starred stories failure")
        starred_stories = {}
    
    # Intelligence classifiers for all feeds involved
    def sort_by_feed(classifiers):
        feed_classifiers = defaultdict(list)
        for classifier in classifiers:
            feed_classifiers[classifier.feed_id].append(classifier)
        return feed_classifiers
    classifiers = {}
    try:
        classifier_feeds   = sort_by_feed(MClassifierFeed.objects(user_id=user.pk, feed_id__in=found_feed_ids))
        classifier_authors = sort_by_feed(MClassifierAuthor.objects(user_id=user.pk, feed_id__in=found_feed_ids))
        classifier_titles  = sort_by_feed(MClassifierTitle.objects(user_id=user.pk, feed_id__in=found_feed_ids))
        classifier_tags    = sort_by_feed(MClassifierTag.objects(user_id=user.pk, feed_id__in=found_feed_ids))
    except OperationFailure:
        logging.info(" ***> Classifiers failure")
    else:
        for feed_id in found_feed_ids:
            classifiers[feed_id] = get_classifiers_for_user(user, feed_id, classifier_feeds[feed_id], 
                                                            classifier_authors[feed_id],
                                                            classifier_titles[feed_id],
                                                            classifier_tags[feed_id])
    
    # Just need to format stories
    for story in stories:
        story_date = localtime_for_timezone(story['story_date'], user.profile.timezone)
        now = localtime_for_timezone(datetime.datetime.now(), user.profile.timezone)
        story['short_parsed_date'] = format_story_link_date__short(story_date, now)
        story['long_parsed_date']  = format_story_link_date__long(story_date, now)
        story['read_status'] = 0
        if story['id'] in starred_stories:
            story['starred'] = True
            starred_date = localtime_for_timezone(starred_stories[story['id']], user.profile.timezone)
            story['starred_date'] = format_story_link_date__long(starred_date, now)
        story['intelligence'] = {
            'feed':   apply_classifier_feeds(classifier_feeds[story['story_feed_id']], story['story_feed_id']),
            'author': apply_classifier_authors(classifier_authors[story['story_feed_id']], story),
            'tags':   apply_classifier_tags(classifier_tags[story['story_feed_id']], story),
            'title':  apply_classifier_titles(classifier_titles[story['story_feed_id']], story),
        }

    diff = time.time() - start
    timediff = round(float(diff), 2)
    logging.user(request, "~FCLoading river stories: page %s - ~SB%s/%s "
                               "stories ~SN(%s/%s/%s feeds) ~FB(%s seconds)" % 
                               (page, len(stories), len(mstories), len(found_feed_ids), 
                               len(feed_ids), len(original_feed_ids), timediff))
    
    return dict(stories=stories, classifiers=classifiers, elapsed_time=timediff)
    
    
@ajax_login_required
@json.json_view
def mark_all_as_read(request):
    code = 1
    days = int(request.POST.get('days', 0))
    
    feeds = UserSubscription.objects.filter(user=request.user)
    for sub in feeds:
        if days == 0:
            sub.mark_feed_read()
        else:
            read_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
            if sub.mark_read_date < read_date:
                sub.needs_unread_recalc = True
                sub.mark_read_date = read_date
                sub.save()
    
    logging.user(request, "~FMMarking all as read: ~SB%s days" % (days,))
    return dict(code=code)
    
@ajax_login_required
@json.json_view
def mark_story_as_read(request):
    story_ids = request.REQUEST.getlist('story_id')
    feed_id = int(get_argument_or_404(request, 'feed_id'))

    try:
        usersub = UserSubscription.objects.select_related('feed').get(user=request.user, feed=feed_id)
    except (UserSubscription.DoesNotExist, Feed.DoesNotExist):
        duplicate_feed = DuplicateFeed.objects.filter(duplicate_feed_id=feed_id)
        if duplicate_feed:
            try:
                usersub = UserSubscription.objects.get(user=request.user, 
                                                       feed=duplicate_feed[0].feed)
            except (UserSubscription.DoesNotExist, Feed.DoesNotExist):
                return dict(code=-1)
        else:
            return dict(code=-1)
    
    data = usersub.mark_story_ids_as_read(story_ids, request=request)
    
    return data
    
@ajax_login_required
@json.json_view
def mark_feed_stories_as_read(request):
    feeds_stories = request.REQUEST.get('feeds_stories', "{}")
    feeds_stories = json.decode(feeds_stories)
    for feed_id, story_ids in feeds_stories.items():
        feed_id = int(feed_id)
        try:
            usersub = UserSubscription.objects.select_related('feed').get(user=request.user, feed=feed_id)
        except (UserSubscription.DoesNotExist, Feed.DoesNotExist):
            duplicate_feed = DuplicateFeed.objects.filter(duplicate_feed_id=feed_id)
            if duplicate_feed:
                try:
                    usersub = UserSubscription.objects.get(user=request.user, 
                                                           feed=duplicate_feed[0].feed)
                except (UserSubscription.DoesNotExist, Feed.DoesNotExist):
                    continue
            else:
                continue
        usersub.mark_story_ids_as_read(story_ids)
    
    return dict(code=1)
    
@ajax_login_required
@json.json_view
def mark_story_as_unread(request):
    story_id = request.POST['story_id']
    feed_id = int(request.POST['feed_id'])

    usersub = UserSubscription.objects.select_related('feed').get(user=request.user, feed=feed_id)
                
    if not usersub.needs_unread_recalc:
        usersub.needs_unread_recalc = True
        usersub.save()
        
    data = dict(code=0, payload=dict(story_id=story_id))
    logging.user(request, "~FY~SBUnread~SN story in feed: %s" % (usersub.feed))
    
    story = MStory.objects(story_feed_id=feed_id, story_guid=story_id)[0]
    
    if story.story_date < usersub.mark_read_date:
        # Story is outside the mark as read range, so invert all stories before.
        newer_stories = MStory.objects(story_feed_id=story.story_feed_id,
                                       story_date__gte=story.story_date,
                                       story_date__lte=usersub.mark_read_date
                                       ).only('story_guid')
        newer_stories = [s.story_guid for s in newer_stories]
        usersub.mark_read_date = story.story_date - datetime.timedelta(minutes=1)
        usersub.needs_unread_recalc = True
        usersub.save()
        
        # Mark stories as read only after the mark_read_date has been moved, otherwise
        # these would be ignored.
        data = usersub.mark_story_ids_as_read(newer_stories, request=request)
        
    m = MUserStory.objects(story_id=story_id, user_id=request.user.pk, feed_id=feed_id)
    m.delete()
    
    return data
    
@ajax_login_required
@json.json_view
def mark_feed_as_read(request):
    feed_ids = [int(f) for f in request.REQUEST.getlist('feed_id') if f]
    feed_count = len(feed_ids)
    multiple = feed_count > 1
    code = 0
    for feed_id in feed_ids:
        try:
            feed = Feed.objects.get(id=feed_id)
        except Feed.DoesNotExist:
            continue
        code = 0
    
        us = UserSubscription.objects.get(feed=feed, user=request.user)
        try:
            if us:
                us.mark_feed_read()
        except IntegrityError:
            code = -1
        else:
            code = 1
        
        if not multiple:
            logging.user(request, "~FMMarking feed as read: ~SB%s" % (feed,))
            
    if multiple:
        logging.user(request, "~FMMarking ~SB%s~SN feeds as read" % (feed_count,))
        
    return dict(code=code)

def _parse_user_info(user):
    return {
        'user_info': {
            'is_anonymous': json.encode(user.is_anonymous()),
            'is_authenticated': json.encode(user.is_authenticated()),
            'username': json.encode(user.username if user.is_authenticated() else 'Anonymous')
        }
    }

@ajax_login_required
@json.json_view
def add_url(request):
    code = 0
    url = request.POST['url']
    if not url:
        code = -1
        message = 'Enter in the website address or the feed URL.'
    else:
        folder = request.POST.get('folder', '')
        code, message, _ = UserSubscription.add_subscription(user=request.user, feed_address=url, folder=folder)
    
    return dict(code=code, message=message)

@ajax_login_required
@json.json_view
def add_folder(request):
    folder = request.POST['folder']
    parent_folder = request.POST.get('parent_folder', '')

    logging.user(request, "~FRAdding Folder: ~SB%s (in %s)" % (folder, parent_folder))
    
    if folder:
        code = 1
        message = ""
        user_sub_folders_object, _ = UserSubscriptionFolders.objects.get_or_create(user=request.user)
        user_sub_folders_object.add_folder(parent_folder, folder)
    else:
        code = -1
        message = "Gotta write in a folder name."
        
    return dict(code=code, message=message)

@ajax_login_required
@json.json_view
def delete_feed(request):
    feed_id = int(request.POST['feed_id'])
    in_folder = request.POST.get('in_folder', '')
    if in_folder == ' ':
        in_folder = ""
    
    user_sub_folders = get_object_or_404(UserSubscriptionFolders, user=request.user)
    user_sub_folders.delete_feed(feed_id, in_folder)
    
    feed = Feed.objects.filter(pk=feed_id)
    if feed:
        feed[0].count_subscribers()
    
    return dict(code=1)
    
@ajax_login_required
@json.json_view
def delete_folder(request):
    folder_to_delete = request.POST.get('folder_name') or request.POST.get('folder_to_delete')
    in_folder = request.POST.get('in_folder', '')
    feed_ids_in_folder = [int(f) for f in request.REQUEST.getlist('feed_id') if f]
    
    # Works piss poor with duplicate folder titles, if they are both in the same folder.
    # Deletes all, but only in the same folder parent. But nobody should be doing that, right?
    user_sub_folders = get_object_or_404(UserSubscriptionFolders, user=request.user)
    user_sub_folders.delete_folder(folder_to_delete, in_folder, feed_ids_in_folder)

    return dict(code=1)
    
@ajax_login_required
@json.json_view
def rename_feed(request):
    feed = get_object_or_404(Feed, pk=int(request.POST['feed_id']))
    user_sub = UserSubscription.objects.get(user=request.user, feed=feed)
    feed_title = request.POST['feed_title']
    
    logging.user(request, "~FRRenaming feed '~SB%s~SN' to: ~SB%s" % (
                 feed.feed_title, feed_title))
                 
    user_sub.user_title = feed_title
    user_sub.save()
    
    return dict(code=1)
    
@ajax_login_required
@json.json_view
def rename_folder(request):
    folder_to_rename = request.POST.get('folder_name') or request.POST.get('folder_to_rename')
    new_folder_name = request.POST['new_folder_name']
    in_folder = request.POST.get('in_folder', '')
    code = 0
    
    # Works piss poor with duplicate folder titles, if they are both in the same folder.
    # renames all, but only in the same folder parent. But nobody should be doing that, right?
    if folder_to_rename and new_folder_name:
        user_sub_folders = get_object_or_404(UserSubscriptionFolders, user=request.user)
        user_sub_folders.rename_folder(folder_to_rename, new_folder_name, in_folder)
        code = 1
    else:
        code = -1
        
    return dict(code=code)
    
@ajax_login_required
@json.json_view
def move_feed_to_folder(request):
    feed_id = int(request.POST['feed_id'])
    in_folder = request.POST.get('in_folder', '')
    to_folder = request.POST.get('to_folder', '')

    user_sub_folders = get_object_or_404(UserSubscriptionFolders, user=request.user)
    user_sub_folders = user_sub_folders.move_feed_to_folder(feed_id, in_folder=in_folder, to_folder=to_folder)

    return dict(code=1, folders=json.decode(user_sub_folders.folders))
    
@ajax_login_required
@json.json_view
def move_folder_to_folder(request):
    folder_name = request.POST['folder_name']
    in_folder = request.POST.get('in_folder', '')
    to_folder = request.POST.get('to_folder', '')
    
    user_sub_folders = get_object_or_404(UserSubscriptionFolders, user=request.user)
    user_sub_folders = user_sub_folders.move_folder_to_folder(folder_name, in_folder=in_folder, to_folder=to_folder)

    return dict(code=1, folders=json.decode(user_sub_folders.folders))
    
@login_required
def add_feature(request):
    if not request.user.is_staff:
        return HttpResponseForbidden()

    code = -1    
    form = FeatureForm(request.POST)
    
    if form.is_valid():
        form.save()
        code = 1
        return HttpResponseRedirect(reverse('index'))
    
    return dict(code=code)
    
@json.json_view
def load_features(request):
    user = get_user(request)
    page = int(request.REQUEST.get('page', 0))
    logging.user(request, "~FBBrowse features: ~SBPage #%s" % (page+1))
    features = Feature.objects.all()[page*3:(page+1)*3+1].values()
    features = [{
        'description': f['description'], 
        'date': localtime_for_timezone(f['date'], user.profile.timezone).strftime("%b %d, %Y")
    } for f in features]
    return features

@ajax_login_required
@json.json_view
def save_feed_order(request):
    folders = request.POST.get('folders')
    if folders:
        # Test that folders can be JSON decoded
        folders_list = json.decode(folders)
        assert folders_list is not None
        logging.user(request, "~FBFeed re-ordering: ~SB%s folders/feeds" % (len(folders_list)))
        user_sub_folders = UserSubscriptionFolders.objects.get(user=request.user)
        user_sub_folders.folders = folders
        user_sub_folders.save()
    
    return {}

@json.json_view
def feeds_trainer(request):
    classifiers = []
    feed_id = request.REQUEST.get('feed_id')
    user = get_user(request)
    usersubs = UserSubscription.objects.filter(user=user, active=True)
    if feed_id:
        feed = get_object_or_404(Feed, pk=feed_id)
        usersubs = usersubs.filter(feed=feed)
    usersubs = usersubs.select_related('feed').order_by('-feed__stories_last_month')
                
    for us in usersubs:
        if (not us.is_trained and us.feed.stories_last_month > 0) or feed_id:
            classifier = dict()
            classifier['classifiers'] = get_classifiers_for_user(user, us.feed.pk)
            classifier['feed_id'] = us.feed.pk
            classifier['stories_last_month'] = us.feed.stories_last_month
            classifier['num_subscribers'] = us.feed.num_subscribers
            classifier['feed_tags'] = json.decode(us.feed.data.popular_tags) if us.feed.data.popular_tags else []
            classifier['feed_authors'] = json.decode(us.feed.data.popular_authors) if us.feed.data.popular_authors else []
            classifiers.append(classifier)
    
    logging.user(user, "~FGLoading Trainer: ~SB%s feeds" % (len(classifiers)))
    
    return classifiers

@ajax_login_required
@json.json_view
def save_feed_chooser(request):
    approved_feeds = [int(feed_id) for feed_id in request.POST.getlist('approved_feeds') if feed_id][:64]
    activated = 0
    usersubs = UserSubscription.objects.filter(user=request.user)
    
    for sub in usersubs:
        try:
            if sub.feed.pk in approved_feeds:
                activated += 1
                if not sub.active:
                    sub.active = True
                    sub.save()
                    sub.feed.count_subscribers()
            elif sub.active:
                sub.active = False
                sub.save()
        except Feed.DoesNotExist:
            pass
            
    
    logging.user(request, "~BB~FW~SBActivated standard account: ~FC%s~SN/~SB%s" % (
        activated, 
        usersubs.count()
    ))
    request.user.profile.queue_new_feeds()
    request.user.profile.refresh_stale_feeds(exclude_new=True)

    return {'activated': activated}

@ajax_login_required
def retrain_all_sites(request):
    for sub in UserSubscription.objects.filter(user=request.user):
        sub.is_trained = False
        sub.save()
        
    return feeds_trainer(request)
    
@login_required
def activate_premium_account(request):
    try:
        usersubs = UserSubscription.objects.select_related('feed').filter(user=request.user)
        for sub in usersubs:
            sub.active = True
            sub.save()
            if sub.feed.premium_subscribers <= 0:
                sub.feed.count_subscribers()
                sub.feed.schedule_feed_fetch_immediately()
    except Exception, e:
        subject = "Premium activation failed"
        message = "%s -- %s\n\n%s" % (request.user, usersubs, e)
        mail_admins(subject, message, fail_silently=True)
        
    request.user.profile.is_premium = True
    request.user.profile.save()
        
    return HttpResponseRedirect(reverse('index'))

@login_required
def login_as(request):
    if not request.user.is_staff:
        logging.user(request, "~SKNON-STAFF LOGGING IN AS ANOTHER USER!")
        assert False
        return HttpResponseForbidden()
    username = request.GET['user']
    user = get_object_or_404(User, username__iexact=username)
    user.backend = settings.AUTHENTICATION_BACKENDS[0]
    login_user(request, user)
    return HttpResponseRedirect(reverse('index'))
    
def iframe_buster(request):
    logging.user(request, "~FB~SBiFrame bust!")
    return HttpResponse(status=204)
    
@ajax_login_required
@json.json_view
def mark_story_as_starred(request):
    code     = 1
    feed_id  = int(request.POST['feed_id'])
    story_id = request.POST['story_id']
    
    story = MStory.objects(story_feed_id=feed_id, story_guid=story_id).limit(1)
    if story:
        story_db = dict([(k, v) for k, v in story[0]._data.items() 
                                if k is not None and v is not None])
        now = datetime.datetime.now()
        story_values = dict(user_id=request.user.pk, starred_date=now, **story_db)
        MStarredStory.objects.create(**story_values)
        logging.user(request, "~FCStarring: ~SB%s" % (story[0].story_title[:50]))
    else:
        code = -1
    
    return {'code': code}
    
@ajax_login_required
@json.json_view
def mark_story_as_unstarred(request):
    code     = 1
    story_id = request.POST['story_id']
    
    starred_story = MStarredStory.objects(user_id=request.user.pk, story_guid=story_id)
    if starred_story:
        logging.user(request, "~FCUnstarring: ~SB%s" % (starred_story[0].story_title[:50]))
        starred_story.delete()
    else:
        code = -1
    
    return {'code': code}

@ajax_login_required
@json.json_view
def send_story_email(request):
    code       = 1
    message    = 'OK'
    story_id   = request.POST['story_id']
    feed_id    = request.POST['feed_id']
    to_address = request.POST['to']
    from_name  = request.POST['from_name']
    from_email = request.POST['from_email']
    comments   = request.POST['comments']
    comments   = comments[:2048] # Separated due to PyLint
    from_address = 'share@newsblur.com'

    if not email_re.match(to_address):
        code = -1
        message = 'You need to send the email to a valid email address.'
    elif not email_re.match(from_email):
        code = -1
        message = 'You need to provide your email address.'
    elif not from_name:
        code = -1
        message = 'You need to provide your name.'
    else:
        story   = MStory.objects(story_feed_id=feed_id, story_guid=story_id)[0]
        story   = Feed.format_story(story, feed_id, text=True)
        feed    = Feed.objects.get(pk=story['story_feed_id'])
        text    = render_to_string('mail/email_story_text.xhtml', locals())
        html    = render_to_string('mail/email_story_html.xhtml', locals())
        subject = "%s is sharing a story with you: \"%s\"" % (from_name, story['story_title'])
        subject = subject.replace('\n', ' ')
        msg     = EmailMultiAlternatives(subject, text, 
                                         from_email='NewsBlur <%s>' % from_address,
                                         to=[to_address], 
                                         cc=['%s <%s>' % (from_name, from_email)],
                                         headers={'Reply-To': '%s <%s>' % (from_name, from_email)})
        msg.attach_alternative(html, "text/html")
        msg.send()
        logging.user(request, '~BMSharing story by email: ~FY~SB%s~SN~BM~FY/~SB%s' % 
                                   (story['story_title'][:50], feed.feed_title[:50]))
        
    return {'code': code, 'message': message}

@json.json_view
def load_tutorial(request):
    if request.REQUEST.get('finished'):
        logging.user(request, '~BY~FW~SBFinishing Tutorial')
        return {}
    else:
        newsblur_feed = Feed.objects.filter(feed_address__icontains='blog.newsblur.com').order_by('-pk')[0]
        logging.user(request, '~BY~FW~SBLoading Tutorial')
        return {
            'newsblur_feed': newsblur_feed.canonical()
        }
