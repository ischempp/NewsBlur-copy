package com.newsblur.database;

import java.util.ArrayList;
import java.util.List;

import android.content.Context;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.widget.SimpleCursorAdapter;
import android.text.TextUtils;
import android.view.View;
import android.widget.TextView;

import com.newsblur.R;
import com.newsblur.domain.Feed;
import com.newsblur.domain.Story;
import com.newsblur.util.PrefsUtils;

public class FeedItemsAdapter extends StoryItemsAdapter {

	private Cursor cursor;
	private final Feed feed;
	private int storyTitleUnread, storyTitleRead, storyContentUnread, storyContentRead, storyAuthorUnread, storyAuthorRead, storyDateUnread, storyDateRead;

	public FeedItemsAdapter(Context context, Feed feed, int layout, Cursor c, String[] from, int[] to, int flags) {
		super(context, layout, c, from, to, flags);
		this.feed = feed;
		this.cursor = c;

        storyTitleUnread = context.getResources().getColor(R.color.story_title_unread);
        storyTitleRead = context.getResources().getColor(R.color.story_title_read);
        storyContentUnread = context.getResources().getColor(R.color.story_content_unread);
        storyContentRead = context.getResources().getColor(R.color.story_content_read);
        storyAuthorUnread = context.getResources().getColor(R.color.story_author_unread);
		storyAuthorRead = context.getResources().getColor(R.color.story_author_read);
		storyDateUnread = context.getResources().getColor(R.color.story_date_unread);
		storyDateRead = context.getResources().getColor(R.color.story_date_read);
	}

	@Override
	public int getCount() {
		return cursor.getCount();
	}

	@Override
	public Cursor swapCursor(Cursor c) {
		this.cursor = c;
		return super.swapCursor(c);
	}

	@Override
	public void bindView(View v, Context context, Cursor cursor) {
        super.bindView(v, context, cursor);

		View borderOne = v.findViewById(R.id.row_item_favicon_borderbar_1);
		View borderTwo = v.findViewById(R.id.row_item_favicon_borderbar_2);

		if (!TextUtils.equals(feed.faviconColor, "#null") && !TextUtils.equals(feed.faviconFade, "#null")) {
			borderOne.setBackgroundColor(Color.parseColor(feed.faviconColor));
			borderTwo.setBackgroundColor(Color.parseColor(feed.faviconFade));
		} else {
			borderOne.setBackgroundColor(Color.GRAY);
			borderTwo.setBackgroundColor(Color.LTGRAY);
		}

		if (! Story.fromCursor(cursor).read) {
			((TextView) v.findViewById(R.id.row_item_author)).setTextColor(storyAuthorUnread);
			((TextView) v.findViewById(R.id.row_item_date)).setTextColor(storyDateUnread);
            ((TextView) v.findViewById(R.id.row_item_title)).setTextColor(storyTitleUnread);
            ((TextView) v.findViewById(R.id.row_item_content)).setTextColor(storyContentUnread);
			
			((TextView) v.findViewById(R.id.row_item_date)).setTypeface(null, Typeface.BOLD);
			((TextView) v.findViewById(R.id.row_item_author)).setTypeface(null, Typeface.BOLD);
			((TextView) v.findViewById(R.id.row_item_title)).setTypeface(null, Typeface.BOLD);
			
			borderOne.getBackground().setAlpha(255);
			borderTwo.getBackground().setAlpha(255);
		} else {
			((TextView) v.findViewById(R.id.row_item_author)).setTextColor(storyAuthorRead);
			((TextView) v.findViewById(R.id.row_item_date)).setTextColor(storyDateRead);
            ((TextView) v.findViewById(R.id.row_item_title)).setTextColor(storyTitleRead);
            ((TextView) v.findViewById(R.id.row_item_content)).setTextColor(storyContentRead);
			
			((TextView) v.findViewById(R.id.row_item_date)).setTypeface(null, Typeface.NORMAL);
			((TextView) v.findViewById(R.id.row_item_author)).setTypeface(null, Typeface.NORMAL);
            ((TextView) v.findViewById(R.id.row_item_title)).setTypeface(null, Typeface.NORMAL);
            ((TextView) v.findViewById(R.id.row_item_content)).setTypeface(null, Typeface.NORMAL);
			borderOne.getBackground().setAlpha(125);
			borderTwo.getBackground().setAlpha(125);
		}

        if (!PrefsUtils.isShowContentPreviews(context)) {
            v.findViewById(R.id.row_item_content).setVisibility(View.GONE);
        }
	}
	
	@Override
	public Story getStory(int position) {
		cursor.moveToPosition(position);
		return Story.fromCursor(cursor);
	}
	
	@Override
	public List<Story> getPreviousStories(int position) {
		List<Story> stories = new ArrayList<Story>();
		cursor.moveToPosition(0);
		for(int i=0;i<=position && position < cursor.getCount();i++) {
			Story story = Story.fromCursor(cursor);
			stories.add(story);
			cursor.moveToNext();
		}
		return stories;
	}

	@Override
	public List<Story> getNextStories(int position) {
		List<Story> stories = new ArrayList<Story>();
		cursor.moveToPosition(position);
		for(int i=position;i<cursor.getCount();i++) {
			Story story = Story.fromCursor(cursor);
			stories.add(story);
			cursor.moveToNext();
		}
		return stories;
	}

}
