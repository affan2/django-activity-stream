from django.conf.urls.defaults import *
from actstream import feeds
from django.urls import re_path

urlpatterns = ('actstream.views',
    # Syndication Feeds
    re_path(r'^feed/(?P<content_type_id>\d+)/(?P<object_id>\d+)/atom/$',
        feeds.AtomObjectActivityFeed(), name='actstream_object_feed_atom'),
    re_path(r'^feed/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        feeds.ObjectActivityFeed(), name='actstream_object_feed'),
    re_path(r'^feed/(?P<content_type_id>\d+)/atom/$',
        feeds.AtomModelActivityFeed(), name='actstream_model_feed_atom'),
    re_path(r'^feed/(?P<content_type_id>\d+)/(?P<object_id>\d+)/as/$',
        feeds.ActivityStreamsObjectActivityFeed(),
        name='actstream_object_feed_as'),
    re_path(r'^feed/(?P<content_type_id>\d+)/$',
        feeds.ModelActivityFeed(), name='actstream_model_feed'),
    re_path(r'^feed/$', feeds.UserActivityFeed(), name='actstream_feed'),
    re_path(r'^feed/atom/$', feeds.AtomUserActivityFeed(),
        name='actstream_feed_atom'),

    # Follow/Unfollow API
    re_path(r'^follow/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'follow_unfollow', name='actstream_follow'),
    re_path(r'^follow_all/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'follow_unfollow', {'actor_only': False}, name='actstream_follow_all'),
    re_path(r'^unfollow/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'follow_unfollow', {'do_follow': False}, name='actstream_unfollow'),

    # Follower and Actor lists
    re_path(r'^followers/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'followers', name='actstream_followers'),
    re_path(r'^actors/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'actor', name='actstream_actor'),
    re_path(r'^actstream_actor_subset/(?P<content_type_id>\d+)/(?P<object_id>\d+)/(?P<sIndex>\d+)/(?P<lIndex>\d+)/$',
        'actstream_actor_subset', name='actstream_actor_subset'),
    re_path(r'^actstream_following/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'actstream_following', name='actstream_following'),
    re_path(r'^actstream_following_subset/(?P<content_type_id>\d+)/(?P<object_id>\d+)/(?P<sIndex>\d+)/(?P<lIndex>\d+)/$',
        'actstream_following_subset', name='actstream_following_subset'),
    re_path(r'^actstream_rebuild_cache/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'actstream_rebuild_cache', name='actstream_rebuild_cache'),  
    re_path(r'^actstream_update_activity/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'actstream_update_activity', name='actstream_update_activity'),
    re_path(r'^actstream_latest_activity_count/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        'actstream_latest_activity_count', name='actstream_latest_activity_count'),
    re_path(r'^actors/(?P<content_type_id>\d+)/$',
        'model', name='actstream_model'),

    re_path(r'^detail/(?P<action_id>\d+)/$', 'detail', name='actstream_detail'),
    re_path(r'^(?P<username>[-\w]+)/$', 'user', name='actstream_user'),
    re_path(r'^action/(?P<action_id>\d+)/share/$', 'shareAction', name='shareAction'),
    re_path(r'^action/(?P<action_id>\d+)/delete/$', 'deleteAction', name='deleteAction'),  
    re_path(r'^$', 'stream', name='actstream'),
    re_path(r'^broadcasters/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$', 'get_broadcasters_info', name='get_broadcasters_info'),
    re_path(r'^broadcasters/object/(?P<content_type_id>\d+)/(?P<object_id>\d+)/range/(?P<sIndex>\d+)/(?P<lIndex>\d+)/$', 'get_broadcasters_chunk_info', name='get_broadcasters_chunk_info'),
)
