from django.urls import re_path, path

from actstream import feeds, views


urlpatterns = [
    # User feeds
    re_path(r'^feed/$', feeds.UserActivityFeed(), name='actstream_feed'),
    re_path(r'^feed/atom/$', feeds.AtomUserActivityFeed(), name='actstream_feed_atom'),
    re_path(r'^feed/json/$', feeds.UserJSONActivityFeed.as_view(), name='actstream_feed_json'),

    # Model feeds
    re_path(
        r'^feed/(?P<content_type_id>[^/]+)/$',
        feeds.ModelActivityFeed(),
        name='actstream_model_feed'
    ),
    re_path(
        r'^feed/(?P<content_type_id>[^/]+)/atom/$',
        feeds.AtomModelActivityFeed(),
        name='actstream_model_feed_atom'
    ),
    re_path(
        r'^feed/(?P<content_type_id>[^/]+)/json/$',
        feeds.ModelJSONActivityFeed.as_view(),
        name='actstream_model_feed_json'
    ),

    # Object feeds
    re_path(
        r'^feed/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/$',
        feeds.ObjectActivityFeed(),
        name='actstream_object_feed'
    ),
    re_path(
        r'^feed/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/atom/$',
        feeds.AtomObjectActivityFeed(),
        name='actstream_object_feed_atom'
    ),
    re_path(
        r'^feed/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/json/$',
        feeds.ObjectJSONActivityFeed.as_view(),
        name='actstream_object_feed_json'
    ),

    # Follow/Unfollow API
    re_path(
        r'^follow/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/(?:(?P<flag>[^/]+)/)?$',
        views.follow_unfollow,
        name='actstream_follow'
    ),
    re_path(
        r'^follow_all/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/(?:(?P<flag>[^/]+)/)?$',
        views.follow_unfollow,
        {'actor_only': False},
        name='actstream_follow_all'
    ),
    re_path(
        r'^unfollow_all/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/(?:(?P<flag>[^/]+)/)?$',
        views.follow_unfollow,
        {'actor_only': False, 'do_follow': False},
        name='actstream_unfollow_all'
    ),
    re_path(
        r'^unfollow/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/(?:(?P<flag>[^/]+)/)?$',
        views.follow_unfollow,
        {'do_follow': False},
        name='actstream_unfollow'
    ),

    # Follower and Actor lists
    re_path(
        r'^followers/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/(?:(?P<flag>[^/]+)/)?$',
        views.followers,
        name='actstream_followers'
    ),
    re_path(
        r'^following/(?P<user_id>[^/]+)/(?:(?P<flag>[^/]+)/)?$',
        views.following,
        name='actstream_following'
    ),
    re_path(
        r'^actors/(?P<content_type_id>[^/]+)/(?P<object_id>[^/]+)/$',
        views.actor,
        name='actstream_actor'
    ),
    re_path(
        r'^actors/(?P<content_type_id>[^/]+)/$',
        views.model,
        name='actstream_model'
    ),

    re_path(
        r'^detail/(?P<action_id>[^/]+)/$',
        views.detail,
        name='actstream_detail'
    ),
    re_path(
        r'^(?P<username>[^/]+)/$',
        views.user,
        name='actstream_user'
    ),
    re_path(
        r'^$',
        views.stream,
        name='actstream'
    ),

    re_path(
        r'^actstream_actor_subset/(?P<content_type_id>\d+)/(?P<object_id>\d+)/(?P<sIndex>\d+)/(?P<lIndex>\d+)/$',
        views.actstream_actor_subset,
        name='actstream_actor_subset'
    ),

    re_path(r'^actstream_following/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.actstream_following, name='actstream_following'),
    re_path(r'^actstream_following_subset/(?P<content_type_id>\d+)/(?P<object_id>\d+)/(?P<sIndex>\d+)/(?P<lIndex>\d+)/$',
        views.actstream_following_subset, name='actstream_following_subset'),
    re_path(r'^actstream_rebuild_cache/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.actstream_rebuild_cache, name='actstream_rebuild_cache'),
    re_path(r'^actstream_actor_rebuild_cache/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.actstream_actor_rebuild_cache, name='actstream_actor_rebuild_cache'),
    re_path(r'^actstream_update_activity/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.actstream_update_activity, name='actstream_update_activity'),
    re_path(r'^actstream_latest_activity_count/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.actstream_latest_activity_count, name='actstream_latest_activity_count'),
    re_path(r'^shareAction/(?P<action_id>\d+)/$', views.shareAction, name='shareAction'),
    re_path(r'^deleteAction/(?P<action_id>\d+)/$', views.deleteAction, name='deleteAction'),
    re_path(
        r'^broadcasters/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.get_broadcasters_info,
        name='get_broadcasters_info'
    ),
]
