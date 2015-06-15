package com.newsblur.activity;

import java.util.ArrayList;
import java.util.List;

import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.AsyncTask;
import android.os.Build;
import android.os.Bundle;
import android.app.DialogFragment;
import android.app.FragmentManager;
import android.app.LoaderManager;
import android.content.Loader;
import android.support.v4.view.ViewPager;
import android.support.v4.view.ViewPager.OnPageChangeListener;
import android.util.Log;
import android.view.KeyEvent;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.SeekBar;
import android.widget.SeekBar.OnSeekBarChangeListener;
import android.widget.Toast;

import butterknife.ButterKnife;
import butterknife.FindView;

import com.newsblur.R;
import com.newsblur.domain.Story;
import com.newsblur.fragment.ReadingItemFragment;
import com.newsblur.fragment.ShareDialogFragment;
import com.newsblur.fragment.TextSizeDialogFragment;
import com.newsblur.service.NBSyncService;
import com.newsblur.util.AppConstants;
import com.newsblur.util.DefaultFeedView;
import com.newsblur.util.FeedSet;
import com.newsblur.util.FeedUtils;
import com.newsblur.util.PrefsUtils;
import com.newsblur.util.ReadFilter;
import com.newsblur.util.StoryOrder;
import com.newsblur.util.StateFilter;
import com.newsblur.util.UIUtils;
import com.newsblur.util.ViewUtils;
import com.newsblur.util.VolumeKeyNavigation;
import com.newsblur.view.NonfocusScrollview.ScrollChangeListener;

public abstract class Reading extends NbActivity implements OnPageChangeListener, OnSeekBarChangeListener, ScrollChangeListener, LoaderManager.LoaderCallbacks<Cursor> {

    public static final String EXTRA_FEEDSET = "feed_set";
	public static final String EXTRA_FEED = "feed";
	public static final String EXTRA_SOCIAL_FEED = "social_feed";
	public static final String EXTRA_POSITION = "feed_position";
	public static final String EXTRA_FOLDERNAME = "foldername";
    public static final String EXTRA_DEFAULT_FEED_VIEW = "default_feed_view";
    public static final String EXTRA_STORY_HASH = "story_hash";
    private static final String TEXT_SIZE = "textsize";
    private static final String BUNDLE_POSITION = "position";
    private static final String BUNDLE_STARTING_UNREAD = "starting_unread";
    private static final String BUNDLE_SELECTED_FEED_VIEW = "selectedFeedView";
    private static final String BUNDLE_IS_FULLSCREEN = "is_fullscreen";

    private static final int OVERLAY_RANGE_TOP_DP = 40;
    private static final int OVERLAY_RANGE_BOT_DP = 60;

    /** The minimum screen width (in DP) needed to show all the overlay controls. */
    private static final int OVERLAY_MIN_WIDTH_DP = 355;

	protected int passedPosition;
	protected StateFilter currentState;
    protected StoryOrder storyOrder;
    protected ReadFilter readFilter;

    // Activities navigate to a particular story by hash.
    // We can find it once we have the cursor.
    private String storyHash;

    protected final Object STORIES_MUTEX = new Object();
	protected Cursor stories;

    @FindView(android.R.id.content) View contentView; // we use this a ton, so cache it
    @FindView(R.id.reading_overlay_left) Button overlayLeft;
    @FindView(R.id.reading_overlay_right) Button overlayRight;
    @FindView(R.id.reading_overlay_progress) ProgressBar overlayProgress;
    @FindView(R.id.reading_overlay_progress_right) ProgressBar overlayProgressRight;
    @FindView(R.id.reading_overlay_progress_left) ProgressBar overlayProgressLeft;
    @FindView(R.id.reading_overlay_text) Button overlayText;
    @FindView(R.id.reading_overlay_send) Button overlaySend;
    
    ViewPager pager;

	protected FragmentManager fragmentManager;
	protected ReadingAdapter readingAdapter;
    private boolean stopLoading;
    protected FeedSet fs;

    // unread count for the circular progress overlay. set to nonzero to activate the progress indicator overlay
    protected int startingUnreadCount = 0;

    private float overlayRangeTopPx;
    private float overlayRangeBotPx;

    private int lastVScrollPos = 0;

    private boolean unreadSearchActive = false;
    private boolean unreadSearchStarted = false;

    private List<Story> pageHistory;

    protected DefaultFeedView defaultFeedView;
    private VolumeKeyNavigation volumeKeyNavigation;

    @Override
	protected void onCreate(Bundle savedInstanceBundle) {
		super.onCreate(savedInstanceBundle);

		setContentView(R.layout.activity_reading);
        ButterKnife.bind(this);

		fragmentManager = getFragmentManager();

        fs = (FeedSet)getIntent().getSerializableExtra(EXTRA_FEEDSET);

        if ((savedInstanceBundle != null) && savedInstanceBundle.containsKey(BUNDLE_POSITION)) {
            passedPosition = savedInstanceBundle.getInt(BUNDLE_POSITION);
        } else {
            passedPosition = getIntent().getIntExtra(EXTRA_POSITION, 0);
        }
        if ((savedInstanceBundle != null) && savedInstanceBundle.containsKey(BUNDLE_STARTING_UNREAD)) {
            startingUnreadCount = savedInstanceBundle.getInt(BUNDLE_STARTING_UNREAD);
        }

        // Only use the storyHash the first time the activity is loaded. Ignore when
        // recreated due to rotation etc.
        if (savedInstanceBundle == null) {
            storyHash = getIntent().getStringExtra(EXTRA_STORY_HASH);
        }

		currentState = (StateFilter) getIntent().getSerializableExtra(ItemsList.EXTRA_STATE);
        storyOrder = PrefsUtils.getStoryOrder(this, fs);
        readFilter = PrefsUtils.getReadFilter(this, fs);
        volumeKeyNavigation = PrefsUtils.getVolumeKeyNavigation(this);

        if ((savedInstanceBundle != null) && savedInstanceBundle.containsKey(BUNDLE_SELECTED_FEED_VIEW)) {
            defaultFeedView = (DefaultFeedView)savedInstanceBundle.getSerializable(BUNDLE_SELECTED_FEED_VIEW);
        } else {
            defaultFeedView = (DefaultFeedView) getIntent().getSerializableExtra(EXTRA_DEFAULT_FEED_VIEW);
        }

        // were we fullscreen before rotation?
        if ((savedInstanceBundle != null) && savedInstanceBundle.containsKey(BUNDLE_IS_FULLSCREEN)) {
            boolean isFullscreen = savedInstanceBundle.getBoolean(BUNDLE_IS_FULLSCREEN, false);
            if (isFullscreen) {
                ViewUtils.hideSystemUI(getWindow().getDecorView());
            }
        }

        // this value is expensive to compute but doesn't change during a single runtime
        this.overlayRangeTopPx = (float) UIUtils.convertDPsToPixels(this, OVERLAY_RANGE_TOP_DP);
        this.overlayRangeBotPx = (float) UIUtils.convertDPsToPixels(this, OVERLAY_RANGE_BOT_DP);

        this.pageHistory = new ArrayList<Story>();

        // this likes to default to 'on' for some platforms
        enableProgressCircle(overlayProgressLeft, false);
        enableProgressCircle(overlayProgressRight, false);
	}

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        if (pager != null) {
            outState.putInt(BUNDLE_POSITION, pager.getCurrentItem());
        }

        if (startingUnreadCount != 0) {
            outState.putInt(BUNDLE_STARTING_UNREAD, startingUnreadCount);
        }

        ReadingItemFragment item = getReadingFragment();
        if (item != null) {
            outState.putSerializable(BUNDLE_SELECTED_FEED_VIEW, item.getSelectedFeedView());
        }

        if (ViewUtils.isSystemUIHidden(getWindow().getDecorView())) {
            outState.putBoolean(BUNDLE_IS_FULLSCREEN, true);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        // this view shows stories, it is not safe to perform cleanup
        this.stopLoading = false;
        // onCreate() in our subclass should have called createLoader(), but sometimes the callback never makes it.
        // this ensures that at least one callback happens after activity re-create.
        getLoaderManager().restartLoader(0, null, this);
    }

    @Override
    protected void onPause() {
        this.stopLoading = true;
        super.onPause();
    }

	@Override
	public Loader<Cursor> onCreateLoader(int loaderId, Bundle bundle) {
        return FeedUtils.dbHelper.getStoriesLoader(fs, currentState);
    }

	@Override
	public void onLoaderReset(Loader<Cursor> loader) {
		readingAdapter.swapCursor(null);
	}

	@Override
	public void onLoadFinished(Loader<Cursor> loader, Cursor cursor) {
        synchronized (STORIES_MUTEX) {
            if (cursor == null) return;

            readingAdapter.swapCursor(cursor);
            stories = cursor;

            if (storyHash != null) {
                skipCursorToStoryHash();
            }

            // if this is the first time we've found a cursor, we know the onCreate chain is done
            if (this.pager == null) {
                setupPager();
            }

            try {
                readingAdapter.notifyDataSetChanged();
            } catch (IllegalStateException ise) {
                // sometimes the pager is already shutting down by the time the callback finishes
                finish();
            }

            if (unreadSearchActive) {
                // if we left this flag high, we were looking for an unread, but didn't find one;
                // now that we have more stories, look again.
                nextUnread();
            }
            checkStoryCount(pager.getCurrentItem());
            updateOverlayNav();
            updateOverlayText();
        }
	}

    private void skipCursorToStoryHash() {
        passedPosition = 0;
        while (stories.moveToNext()) {
            Story story = Story.fromCursor(stories);
            if (story.storyHash.equals(storyHash)) {
                return;
            }
            passedPosition++;
        }
    }

    private void setupPager() {
        pager = (ViewPager) findViewById(R.id.reading_pager);
		pager.setPageMargin(UIUtils.convertDPsToPixels(getApplicationContext(), 1));
        if (PrefsUtils.isLightThemeSelected(this)) {
            pager.setPageMarginDrawable(R.drawable.divider_light);
        } else {
            pager.setPageMarginDrawable(R.drawable.divider_dark);
        }

		pager.setOnPageChangeListener(this);
		pager.setAdapter(readingAdapter);

		pager.setCurrentItem(passedPosition, false);
        // setCurrentItem sometimes fails to pass the first page to the callback, so call it manually
        // for the first one.
        this.onPageSelected(passedPosition); 

        updateOverlayNav();
        enableOverlays();
	}

    /**
     * Query the DB for the current unreadcount for this view.
     */
    private int getUnreadCount() {
        // saved stories and global shared stories don't have unreads
        if (fs.isAllSaved() || fs.isGlobalShared()) return 0;
        return FeedUtils.dbHelper.getUnreadCount(fs, currentState);
    }

	@Override
	public boolean onCreateOptionsMenu(Menu menu) {
		super.onCreateOptionsMenu(menu);
		MenuInflater inflater = getMenuInflater();
		inflater.inflate(R.menu.reading, menu);
		return true;
	}

    @Override
    public boolean onPrepareOptionsMenu(Menu menu) {
        super.onPrepareOptionsMenu(menu);
        if (readingAdapter == null || pager == null) { return false; }
        Story story = readingAdapter.getStory(pager.getCurrentItem());
        if (story == null ) { return false; }
        menu.findItem(R.id.menu_reading_save).setTitle(story.starred ? R.string.menu_unsave_story : R.string.menu_save_story);
        menu.findItem(R.id.menu_reading_fullscreen).setVisible(Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT);
        return true;
    }

	@Override
	public boolean onOptionsItemSelected(MenuItem item) {
        if (pager == null) return false;
		int currentItem = pager.getCurrentItem();
		Story story = readingAdapter.getStory(currentItem);
        if (story == null) return false;

		if (item.getItemId() == android.R.id.home) {
			finish();
			return true;
		} else if (item.getItemId() == R.id.menu_reading_original) {
            Intent i = new Intent(Intent.ACTION_VIEW);
            i.setData(Uri.parse(story.permalink));
            startActivity(i);
			return true;
		} else if (item.getItemId() == R.id.menu_reading_sharenewsblur) {
            DialogFragment newFragment = ShareDialogFragment.newInstance(story, readingAdapter.getSourceUserId());
            newFragment.show(getFragmentManager(), "dialog");
			return true;
		} else if (item.getItemId() == R.id.menu_send_story) {
			FeedUtils.sendStory(story, this);
			return true;
		} else if (item.getItemId() == R.id.menu_textsize) {
			TextSizeDialogFragment textSize = TextSizeDialogFragment.newInstance(PrefsUtils.getTextSize(this));
			textSize.show(getFragmentManager(), TEXT_SIZE);
			return true;
		} else if (item.getItemId() == R.id.menu_reading_save) {
            if (story.starred) {
			    FeedUtils.setStorySaved(story, false, Reading.this);
            } else {
			    FeedUtils.setStorySaved(story, true, Reading.this);
            }
			return true;
        } else if (item.getItemId() == R.id.menu_reading_markunread) {
            this.markStoryUnread(story);
            return true;
		} else if (item.getItemId() == R.id.menu_reading_fullscreen) {
            ViewUtils.hideSystemUI(getWindow().getDecorView());
            return true;
        } else {
			return super.onOptionsItemSelected(item);
		}
	}

    @Override
	protected void handleUpdate(boolean freshData) {
        enableMainProgress(NBSyncService.isFeedSetSyncing(this.fs, this));
        updateOverlayNav();
        if (freshData) updateCursor();
    }

    private void updateCursor() {
        synchronized (STORIES_MUTEX) {
            try {
                getLoaderManager().restartLoader(0, null, this);
            } catch (IllegalStateException ise) {
                ; // our heavy use of async can race loader calls, which it will gripe about, but this
                 //  is only a refresh call, so dropping a refresh during creation is perfectly fine.
            }
        }
    }

    // interface OnPageChangeListener

	@Override
	public void onPageScrollStateChanged(int arg0) {
	}

	@Override
	public void onPageScrolled(int arg0, float arg1, int arg2) {
	}

	@Override
	public void onPageSelected(final int position) {
        new AsyncTask<Void, Void, Void>() {
            @Override
            protected Void doInBackground(Void... params) {
                if (readingAdapter == null) return null;
                Story story = readingAdapter.getStory(position);
                if (story != null) {
                    markStoryRead(story);
                    synchronized (pageHistory) {
                        // if the history is just starting out or the last entry in it isn't this page, add this page
                        if ((pageHistory.size() < 1) || (!story.equals(pageHistory.get(pageHistory.size()-1)))) {
                            pageHistory.add(story);
                        }
                    }
                }

                checkStoryCount(position);
                updateOverlayText();
                return null;
            }
        }.execute();
	}

    // interface ScrollChangeListener

    @Override
    public void scrollChanged(int hPos, int vPos, int currentWidth, int currentHeight) {
        // only update overlay alpha every few pixels. modern screens are so dense that it
        // is way overkill to do it on every pixel
        if (Math.abs(lastVScrollPos-vPos) < 2) return;
        lastVScrollPos = vPos;

        int scrollMax = currentHeight - contentView.getMeasuredHeight();
        int posFromBot = (scrollMax - vPos);

        float newAlpha = 0.0f;
        if ((vPos < this.overlayRangeTopPx) && (posFromBot < this.overlayRangeBotPx)) {
            // if we have a super-tiny scroll window such that we never leave either top or bottom,
            // just leave us at full alpha.
            newAlpha = 1.0f;
        } else if (vPos < this.overlayRangeTopPx) {
            float delta = this.overlayRangeTopPx - ((float) vPos);
            newAlpha = delta / this.overlayRangeTopPx;
        } else if (posFromBot < this.overlayRangeBotPx) {
            float delta = this.overlayRangeBotPx - ((float) posFromBot);
            newAlpha = delta / this.overlayRangeBotPx;
        }
        
        this.setOverlayAlpha(newAlpha);
    }

    private void setOverlayAlpha(final float a) {
        // check to see if the device even has room for all the overlays, moving some to overflow if not
        int widthPX = contentView.getMeasuredWidth();
        boolean overflowExtras = false;
        if (widthPX != 0) {
            float widthDP = UIUtils.px2dp(this, widthPX);
            if ( widthDP < OVERLAY_MIN_WIDTH_DP ){
                overflowExtras = true;
            } 
        }

        final boolean _overflowExtras = overflowExtras;
        runOnUiThread(new Runnable() {
            public void run() {
                UIUtils.setViewAlpha(overlayLeft, a, true);
                UIUtils.setViewAlpha(overlayRight, a, true);
                UIUtils.setViewAlpha(overlayProgress, a, true);
                UIUtils.setViewAlpha(overlayText, a, true);
                UIUtils.setViewAlpha(overlaySend, a, !_overflowExtras);
            }
        });
    }

    /**
     * Make visible and update the overlay UI.
     */
    private void enableOverlays() {
        this.setOverlayAlpha(1.0f);
    }

    /**
     * Update the next/back overlay UI after the read-state of a story changes or we navigate in any way.
     */
    private void updateOverlayNav() {
        int currentUnreadCount = getUnreadCount();
        if (currentUnreadCount > this.startingUnreadCount ) {
            this.startingUnreadCount = currentUnreadCount;
        }
        this.overlayLeft.setEnabled(this.getLastReadPosition(false) != -1);
        this.overlayRight.setText((currentUnreadCount > 0) ? R.string.overlay_next : R.string.overlay_done);
        this.overlayRight.setBackgroundResource((currentUnreadCount > 0) ? R.drawable.selector_overlay_bg_right : R.drawable.selector_overlay_bg_right_done);

        if (this.startingUnreadCount == 0 ) {
            // sessions with no unreads just show a full progress bar
            this.overlayProgress.setMax(1);
            this.overlayProgress.setProgress(1);
        } else {
            int unreadProgress = this.startingUnreadCount - currentUnreadCount;
            this.overlayProgress.setMax(this.startingUnreadCount);
            this.overlayProgress.setProgress(unreadProgress);
        }
        this.overlayProgress.invalidate();

        invalidateOptionsMenu();
    }

    private void updateOverlayText() {
        if (overlayText == null) return;
        runOnUiThread(new Runnable() {
            public void run() {
                ReadingItemFragment item = getReadingFragment();
                if (item == null) return;
                if (item.getSelectedFeedView() == DefaultFeedView.STORY) {
                    overlayText.setBackgroundResource(R.drawable.selector_overlay_bg_text);
                    overlayText.setText(R.string.overlay_text);
                } else {
                    overlayText.setBackgroundResource(R.drawable.selector_overlay_bg_story);
                    overlayText.setText(R.string.overlay_story);
                }
                item.handleUpdate();
            }
        });
    }

    public void onWindowFocusChanged(boolean hasFocus) {
        // this callback is a good API-level-independent way to tell when the root view size/layout changes
        super.onWindowFocusChanged(hasFocus);
        this.contentView = findViewById(android.R.id.content);
        enableOverlays();

        // Ensure that we come out of immersive view if the activity no longer has focus
        if (!hasFocus) {
            ViewUtils.showSystemUI(getWindow().getDecorView());
        }
    }

	/**
     * While navigating the story list and at the specified position, see if it is possible
     * and desirable to start loading more stories in the background.  Note that if a load
     * is triggered, this method will be called again by the callback to ensure another
     * load is not needed and all latches are tripped.
     */
    private void checkStoryCount(int position) {
        if (stories == null ) {
			triggerRefresh(position + AppConstants.READING_STORY_PRELOAD);
        } else {
            if (AppConstants.VERBOSE_LOG) {
                Log.d(this.getClass().getName(), String.format("story %d of %d selected, stopLoad: %b", position, stories.getCount(), stopLoading));
            }
            // if the pager is at or near the number of stories loaded, check for more unless we know we are at the end of the list
            if ((position + AppConstants.READING_STORY_PRELOAD) >= stories.getCount()) {
                triggerRefresh(position + AppConstants.READING_STORY_PRELOAD);
            }
        }
	}

	protected void enableMainProgress(boolean enabled) {
        enableProgressCircle(overlayProgressRight, enabled);
	}

    public void enableLeftProgressCircle(boolean enabled) {
        enableProgressCircle(overlayProgressLeft, enabled);
    }

    private void enableProgressCircle(final ProgressBar view, final boolean enabled) {
        runOnUiThread(new Runnable() {
            public void run() {
                if (enabled) {
                    view.setProgress(0);
                    view.setVisibility(View.VISIBLE);
                } else {
                    view.setProgress(100);
                    view.setVisibility(View.GONE);
                }
            }
        });
	}
        
	private void triggerRefresh(int desiredStoryCount) {
		if (!stopLoading) {
            int currentCount = (stories == null) ? 0 : stories.getCount();
            boolean gotSome = NBSyncService.requestMoreForFeed(fs, desiredStoryCount, currentCount);
            if (gotSome) triggerSync();
		}
    }

    private void markStoryRead(Story story) {
        FeedUtils.markStoryAsRead(story, this);
        enableOverlays();
    }

    private void markStoryUnread(Story story) {
        FeedUtils.markStoryUnread(story, this);
        Toast.makeText(Reading.this, R.string.toast_story_unread, Toast.LENGTH_SHORT).show();
        enableOverlays();
    }

    // NB: this callback is for the text size slider
	@Override
	public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
        float size = AppConstants.READING_FONT_SIZE[progress];
	    PrefsUtils.setTextSize(this, size);
		Intent data = new Intent(ReadingItemFragment.TEXT_SIZE_CHANGED);
		data.putExtra(ReadingItemFragment.TEXT_SIZE_VALUE, size); 
		sendBroadcast(data);
	}

	@Override
	public void onStartTrackingTouch(SeekBar seekBar) {
	}

	@Override
	public void onStopTrackingTouch(SeekBar seekBar) {
	}

    /**
     * Click handler for the righthand overlay nav button.
     */
    public void overlayRight(View v) {
        if (getUnreadCount() <= 0) {
            // if there are no unread stories, go back to the feed list
            Intent i = new Intent(this, Main.class);
            i.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
            startActivity(i);
        } else {
            // if there are unreads, go to the next one
            new AsyncTask<Void, Void, Void>() {
                @Override
                protected Void doInBackground(Void... params) {
                    nextUnread();
                    return null;
                }
            }.execute();
        }
    }

    /**
     * Search our set of stories for the next unread one. 
     */
    private void nextUnread() {
        unreadSearchActive = true;

        // the first time an unread search is triggered, also trigger an activation of unreads, so
        // we don't search for a story that doesn't exist in the cursor
        if (!unreadSearchStarted) {
            FeedUtils.activateAllStories();
            unreadSearchStarted = true;
        }

        boolean unreadFound = false;
        // start searching just after the current story
        int candidate = pager.getCurrentItem() + 1;
        unreadSearch:while (!unreadFound) {
            // if we've reached the end of the list, loop back to the beginning
            if (candidate >= readingAdapter.getCount()) {
                candidate = 0;
            }
            // if we have looped all the way around to the story we are on, there aren't any left
            if (candidate == pager.getCurrentItem()) {
                break unreadSearch;
            }
            Story story = readingAdapter.getStory(candidate);
            if (this.stopLoading) {
                // this activity was ended before we finished. just stop.
                unreadSearchActive = false;
                return;
            } 
            // iterate through the stories in our cursor until we find an unread one
            if (story != null) {
                if (story.read) {
                    candidate++;
                    continue unreadSearch;
                } else {
                    unreadFound = true;
                }
            }
            // if we didn't continue or break, the cursor probably changed out from under us, so stop.
            break unreadSearch;
        }

        if (unreadFound) {
            // jump to the story we found
            final int page = candidate;
            runOnUiThread(new Runnable() {
                public void run() {
                    pager.setCurrentItem(page, true);
                }
            });
            // disable the search flag, as we are done
            unreadSearchActive = false;
        } else {
            // We didn't find a story, so we should trigger a check to see if the API can load any more.
            // First, though, double check that there are even any left, as there may have been a delay
            // between marking an earlier one and double-checking counts.
            if (getUnreadCount() <= 0) {
                unreadSearchActive = false;
            } else {
                // trigger a check to see if there are any more to search before proceeding. By leaving the
                // unreadSearchActive flag high, this method will be called again when a new cursor is loaded
                this.checkStoryCount(readingAdapter.getCount()+1);
            }
        }
    }

    /**
     * Click handler for the lefthand overlay nav button.
     */
    public void overlayLeft(View v) {
        int targetPosition = this.getLastReadPosition(true);
        if (targetPosition != -1) {
            pager.setCurrentItem(targetPosition, true);
        } else {
            Log.e(this.getClass().getName(), "reading history contained item not found in cursor.");
        }
    }

    /**
     * Get the pager position of the last story read during this activity or -1 if there is nothing
     * in the history.
     *
     * @param trimHistory optionally trim the history of the currently displayed page iff the
     *        back button has been pressed.
     */
    private int getLastReadPosition(boolean trimHistory) {
        synchronized (this.pageHistory) {
            // the last item is always the currently shown page, do not count it
            if (this.pageHistory.size() < 2) {
                return -1;
            }
            Story targetStory = this.pageHistory.get(this.pageHistory.size()-2);
            int targetPosition = this.readingAdapter.getPosition(targetStory);
            if (trimHistory && (targetPosition != -1)) {
                this.pageHistory.remove(this.pageHistory.size()-1);
            }
            return targetPosition;
        }
    }

    /**
     * Click handler for the progress indicator on the righthand overlay nav button.
     */
    public void overlayCount(View v) {
        String unreadText = getString((getUnreadCount() == 1) ? R.string.overlay_count_toast_1 : R.string.overlay_count_toast_N);
        Toast.makeText(this, String.format(unreadText, getUnreadCount()), Toast.LENGTH_SHORT).show();
    }

    public void overlaySend(View v) {
        if ((readingAdapter == null) || (pager == null)) return;
		Story story = readingAdapter.getStory(pager.getCurrentItem());
        FeedUtils.sendStory(story, this);
    }

    public void overlayText(View v) {
        ReadingItemFragment item = getReadingFragment();
        if (item == null) return;
        item.switchSelectedFeedView();
        updateOverlayText();
    }

    private ReadingItemFragment getReadingFragment() {
        if (readingAdapter == null || pager == null) { return null; }
        return readingAdapter.getExistingItem(pager.getCurrentItem());
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (isVolumeKeyNavigationEvent(keyCode)) {
            processVolumeKeyNavigationEvent(keyCode);
            return true;
        } else {
            return super.onKeyDown(keyCode, event);
        }
    }

    private boolean isVolumeKeyNavigationEvent(int keyCode) {
        return volumeKeyNavigation != VolumeKeyNavigation.OFF &&
               (keyCode == KeyEvent.KEYCODE_VOLUME_DOWN || keyCode == KeyEvent.KEYCODE_VOLUME_UP);
    }

    private void processVolumeKeyNavigationEvent(int keyCode) {
        if ((keyCode == KeyEvent.KEYCODE_VOLUME_DOWN && volumeKeyNavigation == VolumeKeyNavigation.DOWN_NEXT) ||
            (keyCode == KeyEvent.KEYCODE_VOLUME_UP && volumeKeyNavigation == VolumeKeyNavigation.UP_NEXT)) {
            overlayRight(overlayRight);
        } else {
            overlayLeft(overlayLeft);
        }
    }

    @Override
    public boolean onKeyUp(int keyCode, KeyEvent event) {
        // Required to prevent the default sound playing when the volume key is pressed
        if (isVolumeKeyNavigationEvent(keyCode)) {
            return true;
        } else {
            return super.onKeyUp(keyCode, event);
        }
    }
}
