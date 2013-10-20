//
//  UnreadCountView.m
//  NewsBlur
//
//  Created by Samuel Clay on 10/3/12.
//  Copyright (c) 2012 NewsBlur. All rights reserved.
//

#import <QuartzCore/QuartzCore.h>
#import "UnreadCountView.h"
#import "UIView+TKCategory.h"

static UIFont *indicatorFont = nil;
static UIColor *indicatorWhiteColor = nil;
static UIColor *indicatorBlackColor = nil;
static UIColor *positiveBackgroundColor = nil;
static UIColor *neutralBackgroundColor = nil;
static UIColor *positiveBackgroundShadowColor = nil;
static UIColor *neutralBackgroundShadowColor = nil;
static UIColor *negativeBackgroundColor = nil;
static UIColor *blueBackgroundColor = nil;
static UIColor *blueBackgroundShadowColor = nil;

@implementation UnreadCountView

const int COUNT_HEIGHT = 15;
@synthesize appDelegate;
@synthesize psWidth, psPadding, ntWidth, ntPadding;
@synthesize psCount, ntCount, blueCount;
@synthesize rect;

+ (void) initialize {
    if (self == [UnreadCountView class]) {
        indicatorFont = [UIFont boldSystemFontOfSize:12];
        indicatorWhiteColor = [UIColor whiteColor];
        indicatorBlackColor = [UIColor blackColor];
        
        UIColor *ps = UIColorFromRGB(0x6EA74A);
        UIColor *nt = UIColorFromRGB(0xB3B6AD);
        UIColor *ng = UIColorFromRGB(0xCC2A2E);
        UIColor *blue = UIColorFromRGB(0x11448B);
        positiveBackgroundColor = ps;
        neutralBackgroundColor = nt;
        positiveBackgroundShadowColor = UIColorFromRGB(0x4E872A);
        negativeBackgroundColor = ng;
        neutralBackgroundShadowColor = UIColorFromRGB(0x93968D);
        blueBackgroundColor = blue;
        blueBackgroundShadowColor = UIColorFromRGB(0x01346B);
        //        UIColor *psGrad = UIColorFromRGB(0x559F4D);
        //        UIColor *ntGrad = UIColorFromRGB(0xE4AB00);
        //        UIColor *ngGrad = UIColorFromRGB(0x9B181B);
        //        const CGFloat* psTop = CGColorGetComponents(ps.CGColor);
        //        const CGFloat* psBot = CGColorGetComponents(psGrad.CGColor);
        //        CGFloat psGradient[] = {
        //            psTop[0], psTop[1], psTop[2], psTop[3],
        //            psBot[0], psBot[1], psBot[2], psBot[3]
        //        };
        //        psColors = psGradient;
    }
}

- (void)drawRect:(CGRect)r {
    self.userInteractionEnabled = NO;
    
    return [self drawInRect:r ps:psCount nt:ntCount listType:NBFeedListFolder];
}

- (void)drawInRect:(CGRect)r ps:(int)ps nt:(int)nt listType:(NBFeedListType)listType {
    rect = CGRectInset(r, 12, 12);
    rect.size.width -= 18; // Scrollbar padding
    
    psCount = ps;
    ntCount = nt;
    [self calculateOffsets:ps nt:nt];
    
    int psOffset = ps == 0 ? 0 : psWidth - 20;
    int ntOffset = nt == 0 ? 0 : ntWidth - 20;
    
    if (ps > 0 || blueCount) {
        CGRect rr;
        
        if (listType == NBFeedListSocial) {
            if (UI_USER_INTERFACE_IDIOM() == UIUserInterfaceIdiomPad) {
                rr = CGRectMake(rect.size.width + rect.origin.x - psOffset, 7, psWidth, COUNT_HEIGHT);
            } else {
                rr = CGRectMake(rect.size.width + rect.origin.x - psOffset, 7, psWidth, COUNT_HEIGHT);
            }
        } else if (listType == NBFeedListFolder) {
            rr = CGRectMake(rect.size.width + rect.origin.x - psOffset - 22, 8, psWidth, COUNT_HEIGHT);
        } else {
            rr = CGRectMake(rect.size.width + rect.origin.x - psOffset, 7, psWidth, COUNT_HEIGHT);
        }
        
        if (blueCount) {
            [blueBackgroundShadowColor set];
        } else {
            [positiveBackgroundShadowColor set];
        }
        CGRect rrShadow = CGRectMake(rr.origin.x, rr.origin.y+1, rr.size.width, rr.size.height);
        [UIView drawRoundRectangleInRect:rrShadow withRadius:4];
        
        if (blueCount) {
            [blueBackgroundColor set];
        } else {
            [positiveBackgroundColor set];
        }
        [UIView drawRoundRectangleInRect:rr withRadius:4];
        
        
        NSString *psStr = [NSString stringWithFormat:@"%d", ps];
        CGSize size = [psStr sizeWithAttributes:@{NSFontAttributeName: indicatorFont}];
        float x_pos = (rr.size.width - size.width) / 2;
        float y_pos = (rr.size.height - size.height) / 2;
        
        UIColor *psColor;
        if (blueCount) {
            psColor = indicatorBlackColor;
        } else {
            psColor = positiveBackgroundShadowColor;
        }
        [psStr
         drawAtPoint:CGPointMake(rr.origin.x + x_pos, rr.origin.y + y_pos + 1)
         withAttributes:@{NSFontAttributeName: indicatorFont,
                          NSForegroundColorAttributeName: psColor}];
        
        [psStr
         drawAtPoint:CGPointMake(rr.origin.x + x_pos, rr.origin.y + y_pos)
         withAttributes:@{NSFontAttributeName: indicatorFont,
                          NSForegroundColorAttributeName: indicatorWhiteColor}];
    }
    
    if (nt > 0 && appDelegate.selectedIntelligence <= 0) {        
        CGRect rr;
        if (listType == NBFeedListSocial) {
            if (UI_USER_INTERFACE_IDIOM() == UIUserInterfaceIdiomPad) {
                rr = CGRectMake(rect.size.width + rect.origin.x - psWidth - psPadding - ntOffset, 7, ntWidth, COUNT_HEIGHT);
            } else {
                rr = CGRectMake(rect.size.width + rect.origin.x - psWidth - psPadding - ntOffset, 7, ntWidth, COUNT_HEIGHT);
            }
        } else if (listType == NBFeedListFolder) {
            rr = CGRectMake(rect.size.width + rect.origin.x - psWidth - psPadding - ntOffset - 22, 8, ntWidth, COUNT_HEIGHT);
        } else {
            rr = CGRectMake(rect.size.width + rect.origin.x - psWidth - psPadding - ntOffset, 7, ntWidth, COUNT_HEIGHT);
        }
        
        
        [neutralBackgroundShadowColor set];
        CGRect rrShadow = CGRectMake(rr.origin.x, rr.origin.y+1, rr.size.width, rr.size.height);
        [UIView drawRoundRectangleInRect:rrShadow withRadius:4];
        
        [neutralBackgroundColor set];
        [UIView drawRoundRectangleInRect:rr withRadius:4];        
        
        NSString *ntStr = [NSString stringWithFormat:@"%d", nt];
        CGSize size = [ntStr sizeWithAttributes:@{NSFontAttributeName: indicatorFont}];
        float x_pos = (rr.size.width - size.width) / 2;
        float y_pos = (rr.size.height - size.height) / 2;
        
        [ntStr
         drawAtPoint:CGPointMake(rr.origin.x + x_pos, rr.origin.y + y_pos + 1)
         withAttributes:@{NSFontAttributeName: indicatorFont,
                          NSForegroundColorAttributeName: neutralBackgroundShadowColor}];
        
        [ntStr
         drawAtPoint:CGPointMake(rr.origin.x + x_pos, rr.origin.y + y_pos)
         withAttributes:@{NSFontAttributeName: indicatorFont,
                          NSForegroundColorAttributeName: indicatorWhiteColor}];
    }
}

- (void)calculateOffsets:(int)ps nt:(int)nt {
    psWidth = ps == 0 ? 0 : ps < 10 ? 14 : ps < 100 ? 22 : 28;
    ntWidth = nt == 0 ? 0 : nt < 10 ? 14 : nt < 100 ? 22 : 28;
    
    psPadding = ps == 0 ? 0 : 2;
    ntPadding = nt == 0 ? 0 : 2;
}

- (int)offsetWidth {
    int width = 0;
    if (self.psCount > 0) {
        width += psWidth + psPadding;
    }
    if (self.ntCount > 0 && appDelegate.selectedIntelligence <= 0) {
        width += ntWidth + ntPadding;
    }
    return width;
}

@end
