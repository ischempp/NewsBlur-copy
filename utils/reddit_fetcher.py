import re
import datetime
import dateutil.parser
import praw
from django.conf import settings
from django.utils import feedgenerator
from django.utils.html import linebreaks
from apps.social.models import MSocialServices
from apps.reader.models import UserSubscription
from utils import log as logging

class RedditFetcher:
    
    def __init__(self, feed, options=None):
        self.feed = feed
        self.options = options or {}

    def api(self):
        if not hasattr(self, '_api'):
            self._api = praw.Reddit(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_CLIENT_SECRET,
                user_agent="NewsBlur Reddit Fetcher",
            )
        return self._api
    
    def fetch(self):
        # Common subreddits handled differently
        # Home page
        if self.feed.feed_address == "https://reddit.com/.rss":
            subreddit = self.fetch_subreddit("popular")
        elif self.feed.feed_address == "https://reddit.com/r/all.rss":
            subreddit = self.fetch_subreddit("all")
        elif self.feed.feed_address == "https://reddit.com/r/popular.rss":
            subreddit = self.fetch_subreddit("popular")
        else:
            subreddit_name = self.extract_subreddit_name()
            if not subreddit_name: 
                return
            subreddit = self.fetch_subreddit(subreddit_name)

        data = {}
        data['title'] = subreddit.title
        data['link'] = f"https://reddit.com{subreddit.url}"
        data["description"] = subreddit.public_description
        data["lastBuildDate"] = datetime.datetime.utcnow()
        data["generator"] = "NewsBlur Reddit API Decrapifier - %s" % settings.NEWSBLUR_URL
        data["docs"] = None
        data["feed_url"] = self.feed.feed_address
        rss = feedgenerator.Atom1Feed(**data)
        
        merged_data = []
        
        for submission in subreddit.new(limit=25):
            if submission.stickied:
                continue
            if submission.is_self:
                story_data = self.story_data(submission)
                if story_data:
                    merged_data.append(story_data)
            else:
                story_data = self.link_data(submission)
                if story_data:
                    merged_data.append(story_data)
        
        for story_data in merged_data:
            rss.add_item(**story_data)
        
        return rss.writeString('utf-8')
    
    def extract_subreddit_name(self):
        feed_address = self.feed.feed_address
        subreddit = None
        if '/r/' in feed_address:
            subreddit = feed_address.split('/r/')[-1].split('/')[0]
        elif 'r/' in feed_address:
            subreddit = feed_address.split('r/')[-1].split('/')[0]
        elif 'reddit.com' in feed_address:
            subreddit = feed_address.split('reddit.com/')[-1].split('/')[0]
        elif 'reddit.com' in self.feed.feed_link:
            subreddit = self.feed.feed_link.split('reddit.com/')[-1].split('/')[0]
        elif 'reddit.com' in self.feed.feed_address:
            subreddit = self.feed.feed_address.split('reddit.com/')[-1].split('/')[0]
        
        return subreddit

    def fetch_subreddit(self, subreddit):
        try:
            feed = self.api().subreddit(subreddit)
        except Exception as e:
            logging.debug('   ***> [%-30s] ~FRReddit subreddit failed, disconnecting reddit: %s: %s' % 
                          (self.feed.log_title[:30], self.feed.feed_address, e))
            self.feed.save_feed_history(560, "Reddit Error: %s" % e)
            return {}
        
        return feed

    def story_data(self, submission):
        story_data = {}
        story_data['title'] = submission.title
        story_data['link'] = submission.url
        story_data['description'] = self.process_story_text(submission)
        story_data['author_name'] = submission.author.name
        story_data['categories'] = []
        story_data['unique_id'] = "reddit_post:%s" % submission.id
        story_data['pubdate'] = datetime.datetime.fromtimestamp(submission.created_utc)
        return story_data

    def link_data(self, submission):
        story_data = {}
        story_data['title'] = submission.title
        story_data['link'] = submission.url
        story_data['description'] = self.process_story_text(submission)
        story_data["author_name"] = submission.author.name
        story_data['categories'] = []
        story_data['unique_id'] = "reddit_post:%s" % submission.id
        story_data['pubdate'] = datetime.datetime.fromtimestamp(submission.created_utc)
        return story_data

    def process_story_text(self, submission):
        text = submission.selftext

        # Wrap blocks with four spaces in <pre> tags
        text = re.sub(r'(^\s{4})(.*\n)', r'<pre>\2</pre>', text, flags=re.M)
        # Wrap links in <a> tags
        text = re.sub(r'(https?://[^\s]+)', r'<a href="\1">\1</a>', text, flags=re.M)
        # Wrap image links in <img> tags
        text = re.sub(r'(https?://[^\s]+\.(jpg|jpeg|gif|png))', r'<img src="\1" />', text, flags=re.M)
        # Wrap bold text in <b> tags
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Wrap italics text in <i> tags
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        # Replace newlines with <br> tags
        
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        text = linebreaks(text)

        # Add author and [link] [comments] footer
        permalink = submission.permalink
        if submission.is_self:
            permalink = submission.url
        text = f'{text}\n\n<p>Posted by <a href="https://reddit.com/u/{submission.author.name}">{submission.author.name}</a><br><a href="{permalink}">[link]</a> <a href="{permalink}">[comments]</a></p>'
        
        return text
    
    def favicon_url(self, subreddit=None):
        if not subreddit:
            subreddit_name = self.extract_subreddit_name()
            if not subreddit_name: 
                return

            subreddit = self.fetch_subreddit(subreddit_name)

        return subreddit.icon_img or subreddit.community_icon or subreddit.header_img or subreddit.banner_img
        