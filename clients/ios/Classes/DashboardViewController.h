//
//  DashboardViewController.h
//  NewsBlur
//
//  Created by Roy Yang on 7/10/12.
//  Copyright (c) 2012 NewsBlur. All rights reserved.
//

#import <UIKit/UIKit.h>

@class NewsBlurAppDelegate;
@class InteractionsModule;
@class ActivityModule;
@class FeedbackModule;

@interface DashboardViewController : UIViewController <UIPopoverControllerDelegate, UIWebViewDelegate> {
    NewsBlurAppDelegate *appDelegate;
    InteractionsModule *interactionsModule;
    ActivityModule *activitiesModule;
    UIWebView *feedbackWebView;
    UIToolbar *toolbar;
    UINavigationBar *topToolbar;
    UISegmentedControl *segmentedButton;
}

@property (nonatomic) IBOutlet NewsBlurAppDelegate *appDelegate;
@property (nonatomic) IBOutlet InteractionsModule *interactionsModule;
@property (nonatomic) IBOutlet ActivityModule *activitiesModule;
@property (nonatomic) IBOutlet UIWebView *feedbackWebView;

@property (nonatomic) IBOutlet UINavigationBar *topToolbar;
@property (nonatomic) IBOutlet UIToolbar *toolbar;
@property (nonatomic) IBOutlet UISegmentedControl *segmentedButton;

- (IBAction)doLogout:(id)sender;
- (void)refreshInteractions;
- (void)refreshActivity;
- (IBAction)tapSegmentedButton:(id)sender;
@end
