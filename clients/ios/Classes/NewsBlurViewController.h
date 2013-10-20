//
//  NewsBlurViewController.h
//  NewsBlur
//
//  Created by Samuel Clay on 6/16/10.
//  Copyright NewsBlur 2010. All rights reserved.
//

#import <UIKit/UIKit.h>
#import "NewsBlurAppDelegate.h"
#import "FolderTitleView.h"
#import "ASIHTTPRequest.h"
#import "PullToRefreshView.h"
#import "BaseViewController.h"
#import "WEPopoverController.h"
#import "NBNotifier.h"
#import "IASKAppSettingsViewController.h"
#import "MCSwipeTableViewCell.h"

@class NewsBlurAppDelegate;

@interface NewsBlurViewController : BaseViewController 
<UITableViewDelegate, UITableViewDataSource,
UIAlertViewDelegate, PullToRefreshViewDelegate,
ASIHTTPRequestDelegate, NSCacheDelegate,
WEPopoverControllerDelegate,
UIPopoverControllerDelegate,
IASKSettingsDelegate,
MCSwipeTableViewCellDelegate> {
    NewsBlurAppDelegate *appDelegate;
    
    NSMutableDictionary * activeFeedLocations;
    NSMutableDictionary *stillVisibleFeeds;
    NSMutableDictionary *visibleFolders;
    
    BOOL isOffline;
    BOOL viewShowingAllFeeds;
    PullToRefreshView *pull;
    NSDate *lastUpdate;
    NSCache *imageCache;
    
    UIView *innerView;
	UITableView * feedTitlesTable;
	UIToolbar * feedViewToolbar;
    UISlider * feedScoreSlider;
    UIBarButtonItem * homeButton;
    UIBarButtonItem * addBarButton;
    UIBarButtonItem * settingsBarButton;
    UIBarButtonItem * activitiesButton;
    UISegmentedControl * intelligenceControl;
    WEPopoverController *popoverController;
	Class popoverClass;
    NBNotifier *notifier;
}

@property (nonatomic) IBOutlet NewsBlurAppDelegate *appDelegate;
@property (nonatomic) IBOutlet UIView *innerView;
@property (nonatomic) IBOutlet UITableView *feedTitlesTable;
@property (nonatomic) IBOutlet UIToolbar *feedViewToolbar;
@property (nonatomic) IBOutlet UISlider * feedScoreSlider;
@property (nonatomic) IBOutlet UIBarButtonItem * homeButton;
@property (nonatomic) IBOutlet UIBarButtonItem * addBarButton;
@property (nonatomic) IBOutlet UIBarButtonItem * settingsBarButton;
@property (nonatomic) IBOutlet UIBarButtonItem * activitiesButton;
@property (nonatomic) NSMutableDictionary *activeFeedLocations;
@property (nonatomic) NSMutableDictionary *stillVisibleFeeds;
@property (nonatomic) NSMutableDictionary *visibleFolders;
@property (nonatomic, readwrite) BOOL viewShowingAllFeeds;
@property (nonatomic, readwrite) BOOL isOffline;
@property (nonatomic) PullToRefreshView *pull;
@property (nonatomic) NSDate *lastUpdate;
@property (nonatomic) NSCache *imageCache;
@property (nonatomic) IBOutlet UISegmentedControl * intelligenceControl;
@property (nonatomic, retain) WEPopoverController *popoverController;
@property (nonatomic) NSIndexPath *currentRowAtIndexPath;
@property (strong, nonatomic) IBOutlet UIView *noFocusMessage;
@property (strong, nonatomic) IBOutlet UIBarButtonItem *toolbarLeftMargin;
@property (nonatomic, retain) NBNotifier *notifier;

- (void)layoutForInterfaceOrientation:(UIInterfaceOrientation)interfaceOrientation;
- (void)returnToApp;
- (void)fetchFeedList:(BOOL)showLoader;
- (void)finishedWithError:(ASIHTTPRequest *)request;
- (void)finishLoadingFeedList:(ASIHTTPRequest *)request;
- (void)finishLoadingFeedListWithDict:(NSDictionary *)results;
- (void)finishRefreshingFeedList:(ASIHTTPRequest *)request;
- (void)setUserAvatarLayout:(UIInterfaceOrientation)orientation;
- (void)didSelectSectionHeader:(UIButton *)button;
- (IBAction)selectIntelligence;
- (void)didCollapseFolder:(UIButton *)button;
- (BOOL)isFeedVisible:(id)feedId;
- (void)changeToAllMode;
- (void)calculateFeedLocations;
- (IBAction)sectionTapped:(UIButton *)button;
- (IBAction)sectionUntapped:(UIButton *)button;
- (IBAction)sectionUntappedOutside:(UIButton *)button;
- (void)redrawUnreadCounts;
- (void)showExplainerOnEmptyFeedlist;
+ (int)computeMaxScoreForFeed:(NSDictionary *)feed;
- (void)loadFavicons;
- (void)loadAvatars;
- (void)saveAndDrawFavicons:(ASIHTTPRequest *)request;
- (void)requestFailed:(ASIHTTPRequest *)request;
- (void)refreshFeedList;
- (void)refreshFeedList:(id)feedId;
- (void)pullToRefreshViewShouldRefresh:(PullToRefreshView *)view;
- (void)loadOfflineFeeds;
- (void)showUserProfile;
- (IBAction)showSettingsPopover:(id)sender;
- (IBAction)showInteractionsPopover:(id)sender;
- (NSDate *)pullToRefreshViewLastUpdated:(PullToRefreshView *)view;
- (void)fadeSelectedCell;
- (IBAction)tapAddSite:(id)sender;

- (void)resetToolbar;
- (void)refreshHeaderCounts;
- (void)refreshHeaderCounts:(UIInterfaceOrientation)orientation;

- (void)settingsViewControllerDidEnd:(IASKAppSettingsViewController*)sender;
- (void)settingDidChange:(NSNotification*)notification;

- (void)showRefreshNotifier;
- (void)showCountingNotifier;
- (void)showSyncingNotifier;
- (void)showSyncingNotifier:(float)progress hoursBack:(int)days;
- (void)showCachingNotifier:(float)progress hoursBack:(int)hours;
- (void)showOfflineNotifier;
- (void)showDoneNotifier;
- (void)hideNotifier;

@end
