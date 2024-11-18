NEWSBLUR.Views.StoryDiscoverView = Backbone.View.extend({

    events: {
        "click .NB-feed-story-discover": "toggle_feed_story_discover_dialog",
        "click .NB-sideoption-discover-control-item": "switch_discover_section"
    },

    initialize: function () {
        _.bindAll(this, 'toggle_feed_story_discover_dialog', 'switch_discover_section', 'load_discover_stories');
        this.sideoptions_view = this.options.sideoptions_view;
        this.model.story_discover_view = this;
        this.page = 1;
        this.has_more_results = true;
        this.is_loading = false;
        this.current_section = 'site'; // Default to 'site' view

        // Initialize discover stories collection
        this.discover_stories = new NEWSBLUR.Collections.DiscoverStories();
    },

    switch_discover_section: function (e) {
        e.preventDefault();
        var $section = $(e.currentTarget);

        // Update active state
        this.$('.NB-sideoption-discover-control-item').removeClass('NB-active');
        $section.addClass('NB-active');

        // Get section type
        var section = 'site';
        if ($section.find('a').text().toLowerCase().indexOf('all') >= 0) {
            section = 'all';
        } else if ($section.find('a').text().toLowerCase().indexOf('global') >= 0) {
            section = 'global';
        }

        this.current_section = section;
        this.page = 1;
        this.has_more_results = true;
        this.load_discover_stories();
    },

    load_discover_stories: function () {
        if (this.is_loading || !this.has_more_results) return;

        this.is_loading = true;
        this.show_loading();

        var feed_ids = [];
        if (this.current_section === 'all') {
            feed_ids = NEWSBLUR.assets.feeds.pluck('id');
        } else if (this.current_section === 'site') {
            feed_ids = [this.model.get('story_feed_id')];
        }

        // Configure collection for current view
        this.discover_stories.similar_to_story_hash = this.model.get('story_hash');

        var self = this;
        this.discover_stories.fetch({
            data: {
                feed_ids: feed_ids,
                page: this.page
            },
            success: function (model, response) {
                self.hide_loading();
                self.render_stories(response);
                self.is_loading = false;
                if (!response.discover_stories || _.keys(response.discover_stories).length === 0) {
                    self.has_more_results = false;
                }
            },
            error: function () {
                self.hide_loading();
                self.is_loading = false;
            }
        });
    },

    show_loading: function () {
        this.$('.NB-sideoption-discover-content').html(
            '<div class="NB-discover-loading">' +
            '<div class="NB-loading NB-active"></div>' +
            '</div>'
        );
    },

    hide_loading: function () {
        this.$('.NB-discover-loading').remove();
    },

    render_stories: function (response) {
        var $content = this.$('.NB-sideoption-discover-content');

        if (this.page === 1) {
            $content.empty();
        }

        if (!response.discover_stories || _.keys(response.discover_stories).length === 0) {
            if (this.page === 1) {
                $content.html('<div class="NB-discover-empty">No similar stories found</div>');
            }
            return;
        }

        // Convert discover stories response into Stories collection
        var stories = [];
        _.each(response.discover_stories, function (story) {
            stories.push(story);
        });

        // Create container for story titles
        var $story_titles = $('<div class="NB-story-titles">');

        var stories_collection = new NEWSBLUR.Collections.Stories(stories);
        var story_titles_view = new NEWSBLUR.Views.StoryTitlesView({
            el: $story_titles,
            collection: stories_collection,
            $story_titles: $story_titles,
            override_layout: 'split',
            on_discover: this.discover_stories, // Pass the discover stories collection
            in_popover: this
        });

        $content.append(story_titles_view.render().$el);
        this.page += 1;
    },

    render: function () {
        return this.template({
            story: this.model,
            folders: NEWSBLUR.assets.get_feed(this.model.get('story_feed_id')).in_folders()
        });
    },

    template: _.template('\
    <div class="NB-sideoption-discover-wrapper">\
        <div class="NB-sideoption-discover">\
            <div class="NB-sideoption-discover-controls">\
                <ul class="segmented-control NB-sideoption-discover-control">\
                    <li class="segmented-control-item NB-sideoption-discover-control-item NB-active">\
                        <a href="#">This site</a>\
                    </li>\
                    <% for (var i = 0; i < folders.length; i++) { %>\
                        <% if (folders[i] && folders[i].length) { %>\
                            <li class="segmented-control-item NB-sideoption-discover-control-item">\
                                <a href="#"><%- folders[i] %></a>\
                            </li>\
                        <% } %>\
                    <% } %>\
                    <li class="segmented-control-item NB-sideoption-discover-control-item">\
                        <a href="#">All sites</a>\
                    </li>\
                    <li class="segmented-control-item NB-sideoption-discover-control-item">\
                        <a href="#">Global</a>\
                    </li>\
                </ul>\
            </div>\
            <div class="NB-sideoption-discover-content">\
            </div>\
        </div>\
    </div>\
    '),

    toggle_feed_story_discover_dialog: function (options) {
        options = options || {};
        var $sideoption = this.$('.NB-sideoption.NB-feed-story-discover');
        var $discover = this.$('.NB-sideoption-discover-wrapper');

        if (options.close || ($sideoption.hasClass('NB-active') && !options.resize_open)) {
            // Close
            this.is_open = false;
            this.resize({ close: true });
            NEWSBLUR.reader.blur_to_page();
        } else {
            // Open/resize
            this.is_open = true;
            if (!options.resize_open) {
                this.$('.NB-error').remove();
            }
            $sideoption.addClass('NB-active');

            // Load initial stories
            this.page = 1;
            this.has_more_results = true;
            this.load_discover_stories();

            if (options.animate_scroll) {
                var $scroll_container = NEWSBLUR.reader.$s.$story_titles;
                if (_.contains(['split', 'full'], NEWSBLUR.assets.view_setting(NEWSBLUR.reader.active_feed, 'layout'))) {
                    $scroll_container = this.model.latest_story_detail_view.$el.parent();
                }
                $scroll_container.stop().scrollTo(this.$el, {
                    duration: 600,
                    queue: false,
                    easing: 'easeInOutQuint',
                    offset: this.model.latest_story_detail_view.$el.height() -
                        $scroll_container.height()
                });
            }

            this.resize(options);
        }
    },

    autosize: function () {
        this.resize({ duration: 100, resize_open: true });
    },

    resize: function (options) {
        options = options || {};
        var $sideoption_container = this.$('.NB-feed-story-sideoptions-container');
        var $discover_wrapper = this.$('.NB-sideoption-discover-wrapper');
        var $discover_content = this.$('.NB-sideoption-discover');
        var $story_content = this.$('.NB-feed-story-content,.NB-story-content');
        var $story_comments = this.$('.NB-feed-story-comments');
        var $sideoption = this.$('.NB-feed-story-discover');
        var $tag_input = this.$('.NB-sideoption-discover-tag');

        var $discover_clone = $discover_wrapper.clone();
        $discover_wrapper.after($discover_clone.css({
            'height': 'auto',
            'position': 'absolute',
            'visibility': 'hidden',
            'display': 'block'
        }));
        var sideoption_content_height = $discover_clone.height();
        $discover_clone.remove();
        var new_sideoptions_height = $sideoption_container.height() - $discover_wrapper.height() + sideoption_content_height;

        if (!options.close) {
            $sideoption.addClass('NB-active');
            $discover_wrapper.addClass('NB-active');
        }

        if (!options.resize_open && !options.close) {
            $discover_wrapper.css('height', 'auto');
        }

        $discover_wrapper.animate({
            'height': options.close ? 0 : 'auto'
        }, {
            'duration': options.immediate ? 0 : options.duration || 350,
            'easing': 'easeInOutQuint',
            'queue': false,
            'complete': _.bind(function () {
                if ($tag_input.length == 1) {
                    $tag_input.focus();
                }
                if (NEWSBLUR.app.story_list) {
                    NEWSBLUR.app.story_list.fetch_story_locations_in_feed_view();
                }
                if (options.close) {
                    $sideoption.removeClass('NB-active');
                    $discover_wrapper.removeClass('NB-active');
                }
            }, this)
        });

        if (NEWSBLUR.app.story_list) {
            NEWSBLUR.app.story_list.fetch_story_locations_in_feed_view();
        }
    }

});
