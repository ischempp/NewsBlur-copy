package com.newsblur.activity;

import java.util.ArrayList;
import java.util.List;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.os.AsyncTask;
import android.os.Bundle;
import android.support.v4.app.FragmentTransaction;
import android.widget.Toast;

import com.actionbarsherlock.view.Menu;
import com.actionbarsherlock.view.MenuInflater;
import com.newsblur.R;
import com.newsblur.database.DatabaseConstants;
import com.newsblur.database.FeedProvider;
import com.newsblur.fragment.AllStoriesItemListFragment;
import com.newsblur.fragment.FeedItemListFragment;
import com.newsblur.fragment.MarkAllReadDialogFragment;
import com.newsblur.fragment.SyncUpdateFragment;
import com.newsblur.fragment.MarkAllReadDialogFragment.MarkAllReadDialogListener;
import com.newsblur.network.APIManager;
import com.newsblur.service.SyncService;
import com.newsblur.util.AppConstants;
import com.newsblur.util.PrefConstants;
import com.newsblur.util.PrefsUtils;
import com.newsblur.util.ReadFilter;
import com.newsblur.util.StoryOrder;

public class AllStoriesItemsList extends ItemsList implements MarkAllReadDialogListener {

	private APIManager apiManager;
	private ContentResolver resolver;

	@Override
	protected void onCreate(Bundle bundle) {
		super.onCreate(bundle);

		setTitle(getResources().getString(R.string.all_stories));

		apiManager = new APIManager(this);
		resolver = getContentResolver();
		

		itemListFragment = (AllStoriesItemListFragment) fragmentManager.findFragmentByTag(FeedItemListFragment.FRAGMENT_TAG);
		if (itemListFragment == null) {
			itemListFragment = AllStoriesItemListFragment.newInstance(currentState, getStoryOrder());
			itemListFragment.setRetainInstance(true);
			FragmentTransaction listTransaction = fragmentManager.beginTransaction();
			listTransaction.add(R.id.activity_itemlist_container, itemListFragment, FeedItemListFragment.FRAGMENT_TAG);
			listTransaction.commit();
		}

		syncFragment = (SyncUpdateFragment) fragmentManager.findFragmentByTag(SyncUpdateFragment.TAG);
		if (syncFragment == null) {
			syncFragment = new SyncUpdateFragment();
			fragmentManager.beginTransaction().add(syncFragment, SyncUpdateFragment.TAG).commit();
			triggerRefresh();
		}
	}


	@Override
	public void triggerRefresh() {
		triggerRefresh(1);
	}

	@Override
	public void triggerRefresh(int page) {
		if (!stopLoading) {
			setSupportProgressBarIndeterminateVisibility(true);

            String[] feedIds = new String[0]; // default to a wildcard search

            // if we're in Focus mode, only query for feeds with a nonzero focus count
            if (this.currentState == AppConstants.STATE_BEST) {
                Cursor cursor = resolver.query(FeedProvider.FEEDS_URI, null, DatabaseConstants.FEED_FILTER_FOCUS, null, null);
                List<String> feedList = new ArrayList<String>();
                while (cursor.moveToNext() && (feedList.size() <= AppConstants.MAX_FEED_LIST_SIZE)) {
                    feedList.add(cursor.getString(cursor.getColumnIndex(DatabaseConstants.FEED_ID)));
                }
                feedIds = new String[feedList.size()];
                feedList.toArray(feedIds);
                cursor.close();
            }

			final Intent intent = new Intent(Intent.ACTION_SYNC, null, this, SyncService.class);
			intent.putExtra(SyncService.EXTRA_STATUS_RECEIVER, syncFragment.receiver);
			intent.putExtra(SyncService.EXTRA_TASK_TYPE, SyncService.TaskType.MULTIFEED_UPDATE);
            intent.putExtra(SyncService.EXTRA_TASK_MULTIFEED_IDS, feedIds);
			intent.putExtra(SyncService.EXTRA_TASK_PAGE_NUMBER, Integer.toString(page));
			intent.putExtra(SyncService.EXTRA_TASK_ORDER, getStoryOrder());
			intent.putExtra(SyncService.EXTRA_TASK_READ_FILTER, PrefsUtils.getReadFilterForFolder(this, PrefConstants.ALL_STORIES_FOLDER_NAME));

			startService(intent);
		}
	}


	@Override
	public void markItemListAsRead() {
	    MarkAllReadDialogFragment dialog = MarkAllReadDialogFragment.newInstance(getResources().getString(R.string.all_stories));
        dialog.show(fragmentManager, "dialog");
	}

	@Override
	public boolean onCreateOptionsMenu(Menu menu) {
		super.onCreateOptionsMenu(menu);
		MenuInflater inflater = getSupportMenuInflater();
		inflater.inflate(R.menu.allstories_itemslist, menu);
		return true;
	}

	@Override
	public void closeAfterUpdate() { }


    @Override
    protected StoryOrder getStoryOrder() {
        return PrefsUtils.getStoryOrderForFolder(this, PrefConstants.ALL_STORIES_FOLDER_NAME);
    }

    @Override
    public void updateStoryOrderPreference(StoryOrder newValue) {
        PrefsUtils.setStoryOrderForFolder(this, PrefConstants.ALL_STORIES_FOLDER_NAME, newValue);
    }
    
    @Override
    protected void updateReadFilterPreference(ReadFilter newValue) {
        PrefsUtils.setReadFilterForFolder(this, PrefConstants.ALL_STORIES_FOLDER_NAME, newValue);
    }
    
    @Override
    protected ReadFilter getReadFilter() {
        return PrefsUtils.getReadFilterForFolder(this, PrefConstants.ALL_STORIES_FOLDER_NAME);
    }

    @Override
    public void onMarkAllRead() {
        new AsyncTask<Void, Void, Boolean>() {
            @Override
            protected Boolean doInBackground(Void... arg) {
                return apiManager.markAllAsRead();
            }
            
            @Override
            protected void onPostExecute(Boolean result) {
                if (result) {
                    // mark all feed IDs as read
                    ContentValues values = new ContentValues();
                    values.put(DatabaseConstants.FEED_NEGATIVE_COUNT, 0);
                    values.put(DatabaseConstants.FEED_NEUTRAL_COUNT, 0);
                    values.put(DatabaseConstants.FEED_POSITIVE_COUNT, 0);
                    resolver.update(FeedProvider.FEEDS_URI, values, null, null);
                    setResult(RESULT_OK); 
                    Toast.makeText(AllStoriesItemsList.this, R.string.toast_marked_all_stories_as_read, Toast.LENGTH_SHORT).show();
                    finish();
                } else {
                    Toast.makeText(AllStoriesItemsList.this, R.string.toast_error_marking_feed_as_read, Toast.LENGTH_SHORT).show();
                }
            };
        }.execute();
    }

    @Override
    public void onCancel() {
        // do nothing
    }
}
