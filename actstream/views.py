from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.template.loader import render_to_string
from django.http import HttpResponseRedirect, HttpResponse

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt
from django.utils import simplejson
from django.db.models import Q
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.core.urlresolvers import reverse
from userProfile.views import deleteObject
from userProfile.models import GenericWish
from actstream import actions, models
from actstream.models import Follow
from django.core.cache import cache
from actstream import action
from django.utils.translation import ugettext_lazy as _
from mezzanine.blog.models import BlogPost
from actstream.models import Action
from follow.models import Follow as _Follow
from follow import utils
from datetime import timedelta
import datetime
try:
    from django.utils import timezone
    now = timezone.now
except ImportError:
    from datetime import datetime
    now = datetime.now
import itertools

ACTIVITY_DEFAULT_BATCH_TIME = 30

def respond(request, code):
    """
    Responds to the request with the given response code.
    If ``next`` is in the form, it will redirect instead.
    """
    if 'next' in request.REQUEST:
        return HttpResponseRedirect(request.REQUEST['next'])
    return type('Response%d' % code, (HttpResponse, ), {'status_code': code})()


@login_required
@csrf_exempt
def follow_unfollow(request, content_type_id, object_id, do_follow=True, actor_only=True):
    """
    Creates or deletes the follow relationship between ``request.user`` and the
    actor defined by ``content_type_id``, ``object_id``.
    """
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)

    if do_follow:
        actions.follow(request.user, actor, actor_only=actor_only)
        return respond(request, 201)   # CREATED
    actions.unfollow(request.user, actor)
    return respond(request, 204)   # NO CONTENT

@login_required
def stream(request):
    """
    Index page for authenticated user's activity stream. (Eg: Your feed at
    github.com)
    """
    return render_to_response(('actstream/actor.html', 'activity/actor.html'), {
        'ctype': ContentType.objects.get_for_model(User),
        'actor': request.user, 'action_list': models.user_stream(request.user)
    }, context_instance=RequestContext(request))


def followers(request, content_type_id, object_id):
    """
    Creates a listing of ``User``s that follow the actor defined by
    ``content_type_id``, ``object_id``.
    """
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)
    return render_to_response(('actstream/followers.html', 'activity/followers.html'), {
        'followers': models.followers(actor), 'actor': actor
    }, context_instance=RequestContext(request))


def following(request, user_id):
    """
    Returns a list of actors that the user identified by ``user_id`` is following (eg who im following).
    """
    user = get_object_or_404(User, pk=user_id)
    return render_to_response(('actstream/following.html', 'activity/following.html'), {
        'following': models.following(user), 'user': user
    }, context_instance=RequestContext(request))


def user(request, username):
    """
    ``User`` focused activity stream. (Eg: Profile page twitter.com/justquick)
    """
    user = get_object_or_404(User, username=username, is_active=True)
    return render_to_response(('actstream/actor.html', 'activity/actor.html'), {
        'ctype': ContentType.objects.get_for_model(User),
        'actor': user, 'action_list': models.user_stream(user)
    }, context_instance=RequestContext(request))


def detail(request, action_id):
    """
    ``Action`` detail view (pretty boring, mainly used for get_absolute_url)
    """
    return render_to_response(('actstream/detail.html', 'activity/detail.html'), {
        'action': get_object_or_404(models.Action, pk=action_id)
    }, context_instance=RequestContext(request))


def actstream_following(request, content_type_id, object_id):
    from itertools import chain
    import operator
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)
    activity = actor.actor_actions.public()
    
    for followedActor in Follow.objects.following(user=actor):
        target_content_type = ContentType.objects.get_for_model(followedActor)
        prevFollowActions = Action.objects.all().filter(actor_content_type=ctype, actor_object_id=object_id,verb=settings.FOLLOW_VERB, target_content_type=target_content_type, target_object_id = followedActor.pk ).order_by('-pk')
        followAction = None
        if prevFollowActions:
            followAction =  prevFollowActions[0]
        if followAction:
            stream = followedActor.actor_actions.public(timestamp__gte = followAction.timestamp)
            activity = activity | stream

        if not isinstance(followedActor, User):
            _follow = _Follow.objects.get_follows(followedActor)
            if _follow:
                try:     
                    follow = _follow.get(user=actor)
                except (MultipleObjectsReturned, _Follow.DoesNotExist) as e:
                    if isinstance(e, MultipleObjectsReturned):
                        follow = _follow.filter(user=actor)[0]
                        pass
                    else:
                        follow = None
                        pass
                        
                if follow:        
                    stream = models.action_object_stream(followedActor, timestamp__gte = follow.datetime )
                    activity = activity | stream 
                    stream = models.target_stream(followedActor, timestamp__gte = follow.datetime )
                    activity = activity | stream
    activity =  activity.order_by('-timestamp')

    return render_to_response(('actstream/actor_feed.html', 'activity/actor_feed.html'), {
       'action_list': activity, 'actor': actor,
       'ctype': ctype, 'sIndex':0
    }, context_instance=RequestContext(request))


def get_actions_following(request, content_type_id, object_id):
    activity_queryset = None
    ctype 			  = get_object_or_404(ContentType, pk=content_type_id)
    actor 			  = get_object_or_404(ctype.model_class(), pk=object_id)

    if activity_queryset is None:    	
        activity_queryset = actor.actor_actions.public()

        for followedObject in Follow.objects.following(user=actor):
            if followedObject:
                obj_content_type 	  = ContentType.objects.get_for_model(followedObject)
                followObject     	  = Follow.objects.get(user=actor, content_type=obj_content_type, object_id=followedObject.pk )
                if followObject:
                    stream 		 	  = followedObject.actor_actions.public()#timestamp__gte=followObject.started)
                    activity_queryset = activity_queryset | stream

                if not isinstance(followedObject, User) and not isinstance(followedObject, BlogPost):           
                    _follow    = _Follow.objects.get_follows(followedObject)
                    if _follow:
                        follow = None     
                        try:
                            follow = _follow.get(user=actor)
                        except (MultipleObjectsReturned, _Follow.DoesNotExist) as e:
                            if isinstance(e, MultipleObjectsReturned):
                                follow = _follow.filter(user=actor)[0]
                                pass
                            else:
                                follow = None
                                pass

                        if follow:        
                            stream 			  = models.action_object_stream(followedObject)#, timestamp__gte = follow.datetime )
                            activity_queryset = activity_queryset | stream 
                            stream 			  = models.target_stream(followedObject)#, timestamp__gte = follow.datetime )
                            activity_queryset = activity_queryset | stream
        
        allowed_verbs_for_user_in_common_feed = [settings.SAID_VERB, settings.SHARE_VERB, settings.REVIEW_POST_VERB, settings.DEAL_POST_VERB, settings.WISH_POST_VERB]
        user_ctype = ContentType.objects.get_for_model(request.user)
        activity_queryset = activity_queryset.exclude(~Q(verb__in=allowed_verbs_for_user_in_common_feed) & Q(actor_content_type=user_ctype, actor_object_id=request.user.id) )

        followed_blog_posts = utils.get_following_vendors_for_user(request.user)

        blogPostContentType = ContentType.objects.get_for_model(BlogPost)
        if followed_blog_posts:
            activity_queryset = activity_queryset.exclude(Q(verb=settings.REVIEW_POST_VERB) & Q(action_object_content_type=blogPostContentType) & Q(action_object_object_id__in=[blogpost.id for blogpost in followed_blog_posts]))

        activity_queryset = activity_queryset.order_by('-timestamp')

    return activity_queryset

def merge_action_subset_op(request, activity_queryset, sIndex, lIndex):
    activities = activity_queryset[sIndex:lIndex]

    if activities and len(activities) > 0 and 'last_processed_action' not in request.session:
    	request.session['last_processed_action'] = activities[0].id

    batched_actions = request.session.get('batched_following_actions', dict())

    if not batched_actions:
        batched_actions = dict()

    for activity in activities:
        if activity.is_batchable:
            is_batched=False
            
            for value in batched_actions.values():
                if activity.id in value:
                    is_batched = True

            if not is_batched:
                batch_minutes = activity.batch_time_minutes
                if not batch_minutes:
                    batch_minutes = ACTIVITY_DEFAULT_BATCH_TIME

                cutoff_time = activity.timestamp - timedelta(minutes=batch_minutes)

                groupable_activities = Action.objects.none()

                if activity.verb == settings.FOLLOW_VERB:
                    actor_content_type   = ContentType.objects.get_for_model(activity.actor)
                    groupable_activities = activity_queryset.filter(timestamp__gte=cutoff_time,timestamp__lte=activity.timestamp, actor_content_type=actor_content_type, actor_object_id=activity.actor.pk, verb=activity.verb,target_content_type=activity.target_content_type ).exclude(id=activity.id).order_by('-timestamp')
         
                else: 
                    actor_content_type   = ContentType.objects.get_for_model(activity.actor)
                    groupable_activities = activity_queryset.filter(timestamp__gte=cutoff_time, timestamp__lte=activity.timestamp, actor_content_type=actor_content_type, verb=activity.verb,target_content_type=activity.target_content_type, target_object_id=activity.target.id ).exclude(id=activity.id).order_by('-timestamp')

                for gact in groupable_activities:
                    if activity.id in batched_actions:
                        if gact.id not in batched_actions[activity.id]:
                            batched_actions[activity.id].append(gact.id)
                    else:
                        batched_actions[activity.id] =  [gact.id]

    return batched_actions

def actstream_following_subset(request, content_type_id, object_id, sIndex, lIndex):
    
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)

    activity_queryset = get_actions_following(request, content_type_id, object_id)    

    s = (int)(""+sIndex)
    l = (int)(""+lIndex)

    if s == 0 and 'batched_following_actions' in request.session:
        del request.session['batched_following_actions']

    activities = activity_queryset[s:l]
    
    if len(activities) == 0 and s != 0:
        ret_data = {
            'html': 'None',
            'more': False,
            'success': True
        }
        return HttpResponse(simplejson.dumps(ret_data), mimetype="application/json")

    batched_actions = merge_action_subset_op(request, activity_queryset, s, l)
    merged_batch_actions = request.session.get('batched_following_actions',  dict())
    merged_batch_actions.update(batched_actions)
    request.session['batched_following_actions'] = merged_batch_actions

    batched_ids = []
    for k, v in merged_batch_actions.items():
        batched_ids += v

    current_batched_ids = [ activity.id for activity in activities if activity.id not in batched_ids ]

    if len(current_batched_ids) == 0:
        ret_data = {
            'html': 'None',
            'more':True,
            'success': True
        }
        return HttpResponse(simplejson.dumps(ret_data), mimetype="application/json")


    activity_count = 0
    if activity_queryset:
        activity_count = activity_queryset.count()

    if 'last_activity_count' not in request.session:
        request.session['last_activity_count'] = activity_count

    if activities and len(activities) > 0 and s == 0:
        request.session['last_processed_action'] = activities[0].id

    context = RequestContext(request)
    context.update({
           'action_list': activities, 
           'actor': actor,
           'ctype': ctype,
           'sIndex':s,
           'batched_actions':merged_batch_actions
        })

    ret_data = {
        'html': render_to_string(('actstream/actor_feed.html', 'activity/actor_feed.html'), context_instance=context).strip(),
        'success': True,
        'more':True
    }
    return HttpResponse(simplejson.dumps(ret_data), mimetype="application/json")

    # return render_to_response(('actstream/actor_feed.html', 'activity/actor_feed.html'), {
    #    'action_list': activities, 
    #    'actor': actor,
    #    'ctype': ctype,
    #    'sIndex':s,
    #    'batched_actions':merged_batch_actions,
    # }, context_instance=RequestContext(request))

def actstream_latest_activity_count(request, content_type_id, object_id):
    batched_actions   = dict()
    ctype             = get_object_or_404(ContentType, pk=content_type_id)
    actor 			  = get_object_or_404(ctype.model_class(), pk=object_id)

    activity_queryset = get_actions_following(request, content_type_id, object_id)

    last_processed_id = request.session.get('last_processed_action', -1)

    activity_qs_unprocessed = None

    if last_processed_id >= 0:
        """
            Feeds for like/unfollow are excluded in incremental update as user can keep toggling them due to which 
            possibility of duplciation arises.
        """
        disallowed_verbs_for_incremental_feed = [settings.WISH_LIKE_VERB, settings.DEAL_LIKE_VERB, settings.POST_LIKE_VERB, \
    											 settings.ALBUM_LIKE_WISH, settings.REVIEW_COMMENT_LIKE_VERB, settings.ALBUM_COMMENT_LIKE_VERB, \
    											 settings.IMAGE_COMMENT_LIKE_VERB, settings.DEAL_COMMENT_LIKE_VERB, settings.WISH_COMMENT_LIKE_VERB,\
    											 settings.POST_COMMENT_LIKE_VERB, settings.REVIEW_LIKE_VERB, settings.PHOTO_LIKE_VERB,\
    											 settings.FOLLOW_VERB, settings.UNFOLLOW_VERB ]

        activity_qs_unprocessed = activity_queryset.filter(id__gt=last_processed_id).exclude(Q(verb__in=disallowed_verbs_for_incremental_feed))

        if activity_qs_unprocessed and activity_qs_unprocessed.count() > 0:
            batched_actions = merge_action_subset_op(request, activity_qs_unprocessed, 0, activity_qs_unprocessed.count()-1)

        batched_ids = []
        try:
            user = request.user
            
            action_id_maps = batched_actions
            action_id_list = []
            if action_id_maps:
                for k, v in action_id_maps.items():
                    batched_ids += v
        except VariableDoesNotExist:
            return ''

        activity_qs_unprocessed = activity_qs_unprocessed.exclude(id__in=batched_ids)
    
    activity_count = 0
    if activity_qs_unprocessed:
        activity_count = activity_qs_unprocessed.count()
    return HttpResponse(simplejson.dumps(dict(success=True, count=activity_count)))    	

def actstream_update_activity(request, content_type_id, object_id): 
    batched_actions   = dict()
    ctype             = get_object_or_404(ContentType, pk=content_type_id)
    actor 			  = get_object_or_404(ctype.model_class(), pk=object_id)

    activity_queryset = get_actions_following(request, content_type_id, object_id)

    last_processed_id = request.session.get('last_processed_action', -1)

    if last_processed_id >= 0:
    	"""
    		Feeds for like/unfollow are excluded in incremental update as user can keep toggling them due to which 
    		possibility of duplciation arises.
    	"""
    	disallowed_verbs_for_incremental_feed = [settings.WISH_LIKE_VERB, settings.DEAL_LIKE_VERB, settings.POST_LIKE_VERB, \
    											 settings.ALBUM_LIKE_WISH, settings.REVIEW_COMMENT_LIKE_VERB, settings.ALBUM_COMMENT_LIKE_VERB, \
    											 settings.IMAGE_COMMENT_LIKE_VERB, settings.DEAL_COMMENT_LIKE_VERB, settings.WISH_COMMENT_LIKE_VERB,\
    											 settings.POST_COMMENT_LIKE_VERB, settings.REVIEW_LIKE_VERB, settings.PHOTO_LIKE_VERB,\
    											 settings.FOLLOW_VERB, settings.UNFOLLOW_VERB ]

        activity_qs_unprocessed = activity_queryset.filter(id__gt=last_processed_id).exclude(Q(verb__in=disallowed_verbs_for_incremental_feed))

        lastCount 								= request.session.get('last_activity_count', 0)
        request.session['last_activity_count']  = lastCount + activity_qs_unprocessed.count()
        
        if activity_qs_unprocessed and activity_qs_unprocessed.count() > 0 and 'last_processed_action' in request.session:
            request.session['last_processed_action'] = activity_qs_unprocessed[0].id

        if activity_qs_unprocessed and activity_qs_unprocessed.count() > 0:
            batched_actions = merge_action_subset_op(request, activity_qs_unprocessed, 0, activity_qs_unprocessed.count()-1)

            prev_batched_actions = request.session.get('batched_following_actions', dict())

            if prev_batched_actions:
    	        combined_batch_actions = prev_batched_actions.copy()
    	        combined_batch_actions.update(batched_actions)
            else:
    	        combined_batch_actions = batched_actions

            request.session['batched_following_actions'] = combined_batch_actions
        return render_to_response(('actstream/actor_feed.html', 'activity/actor_feed.html'), {
           'action_list': activity_qs_unprocessed,
           'actor': actor,
           'ctype': ctype,
           'sIndex':request.session.get('last_activity_count', 0),
           'batched_actions':batched_actions,
        }, context_instance=RequestContext(request))
    else:
    	"""
    		If last_action_id is not set but there are some unprocessed initial activities, process them.
    	"""
    	if activity_queryset and activity_queryset.count() > 0:
            request.session['last_processed_action'] = activity_queryset[0].id
            request.session['last_activity_count']  = activity_queryset.count()
            return render_to_response(('actstream/actor_feed.html', 'activity/actor_feed.html'), {
               'action_list': activity_queryset,
               'actor': actor,
               'ctype': ctype,
               'sIndex':request.session.get('last_activity_count', 0),
               'batched_actions':batched_actions,
            }, context_instance=RequestContext(request))
    	else:
    	    return HttpResponse('None')
    	    
    return HttpResponse('None')

def actstream_rebuild_cache(request, content_type_id, object_id):
    if 'last_processed_action' in request.session:
    	del request.session['last_processed_action']

    if 'last_activity_count' in request.session:
    	request.session['last_activity_count'] = -1

    return HttpResponse(simplejson.dumps(dict(success=True, message="Cache Updated")))

def actor(request, content_type_id, object_id):
    """
    ``Actor`` focused activity stream for actor defined by ``content_type_id``,
    ``object_id``.
    """
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)
    return render_to_response(('actstream/actor.html', 'activity/actor.html'), {
        'action_list': models.actor_stream(actor), 'actor': actor,
        'ctype': ctype
    }, context_instance=RequestContext(request))

def json_error_response(error_message):
    return HttpResponse(simplejson.dumps(dict(success=False,
                                              error_message=error_message)))

def merge_actor_actions_subset_op(request, activity_queryset, sIndex, lIndex):
    activities = activity_queryset[sIndex:lIndex]

    batched_actions = request.session.get('batched_actor_actions', dict())
    if not batched_actions:
        batched_actions = dict()

    for activity in activities:
        if activity.is_batchable:
            is_batched=False
            
            for value in batched_actions.values():
                if activity.id in value:
                    is_batched = True

            if not is_batched:
                batch_minutes = activity.batch_time_minutes
                if not batch_minutes:
                    batch_minutes = ACTIVITY_DEFAULT_BATCH_TIME

                cutoff_time = activity.timestamp - timedelta(minutes=batch_minutes)

                groupable_activities = Action.objects.none()

                if activity.verb == settings.FOLLOW_VERB:
                    actor_content_type   = ContentType.objects.get_for_model(activity.actor)
                    groupable_activities = activity_queryset.filter(timestamp__gte=cutoff_time,timestamp__lte=activity.timestamp, actor_content_type=actor_content_type, actor_object_id=activity.actor.pk, verb=activity.verb,target_content_type=activity.target_content_type ).exclude(id=activity.id).order_by('-timestamp')
         
                for gact in groupable_activities:
                    if activity.id in batched_actions:
                        if gact.id not in batched_actions[activity.id]:
                            batched_actions[activity.id].append(gact.id)
                    else:
                        batched_actions[activity.id] =  [gact.id]

    return batched_actions

def actstream_actor_subset(request, content_type_id, object_id, sIndex, lIndex):
    """
    ``Actor`` focused activity stream for actor defined by ``content_type_id``,
    ``object_id``.
    """
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)
 
    activity_queryset = models.actor_stream(actor).order_by('-timestamp') 

    s = (int)(""+sIndex)
    l = (int)(""+lIndex)

    if s == 0 and 'batched_actor_actions' in request.session:
        del request.session['batched_actor_actions']

    activities = activity_queryset[s:l]
    if len(activities) == 0 and s != 0:
        ret_data = {
            'html': 'None',
            'more': False,
            'success': True
        }
        return HttpResponse(simplejson.dumps(ret_data), mimetype="application/json")

    batched_actions = merge_actor_actions_subset_op(request, activity_queryset, s, l)
    merged_batch_actions = request.session.get('batched_actor_actions',  dict())
    merged_batch_actions.update(batched_actions)
    request.session['batched_actor_actions'] = merged_batch_actions

    batched_ids = []
    for k, v in merged_batch_actions.items():
        batched_ids += v

    current_batched_ids = [ activity.id for activity in activities if activity.id not in batched_ids ]

    if len(current_batched_ids) == 0:
        ret_data = {
            'html': 'None',
            'more':True,
            'success': True
        }
        return HttpResponse(simplejson.dumps(ret_data), mimetype="application/json")

    context = RequestContext(request)
    context.update({
            'action_list': activities,
            'actor': actor,
            'ctype': ctype,
            'timeline': "true",
            'batched_actions':merged_batch_actions
        })

    ret_data = {
        'html': render_to_string(('actstream/actor_feed.html', 'activity/actor_feed.html'), context_instance=context).strip(),
        'success': True,
        'more':True
    }
    return HttpResponse(simplejson.dumps(ret_data), mimetype="application/json")
    # return render_to_response(('actstream/actor_feed.html', 'activity/actor_feed.html'), {
    #    'action_list': activity, 'actor': actor,
    #    'ctype': ctype,
    #    'timeline': "true",
    #    'batched_actions':merged_batch_actions,
    #    'sIndex':s,
    # }, context_instance=RequestContext(request))


def model(request, content_type_id):
    """
    ``Actor`` focused activity stream for actor defined by ``content_type_id``,
    ``object_id``.
    """
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = ctype.model_class()
    return render_to_response(('actstream/actor.html', 'activity/actor.html'), {
        'action_list': models.model_stream(actor), 'ctype': ctype,
        'actor': ctype
    }, context_instance=RequestContext(request))

def shareAction(request, action_id):

    actionObject = get_object_or_404(models.Action, pk=action_id)
    action.send(request.user, verb=settings.SHARE_VERB, target=actionObject)
    target_content_type = ContentType.objects.get_for_model(actionObject)
    shareCount = Action.objects.filter(verb=settings.SHARE_VERB, target_content_type=target_content_type, target_object_id = actionObject.pk).count()
    if request.is_ajax():
        return HttpResponse(simplejson.dumps(dict(success=True, count=shareCount)))
    else:
        return render_to_response(('actstream/detail.html', 'activity/detail.html'), {
                'action': actionObject
                }, context_instance=RequestContext(request))    


def deleteAction(request, action_id):
    if not request.is_ajax():
       return json_error_response('only supported with AJAX')

    actionObject = get_object_or_404(models.Action, pk=action_id)
    blog_posts = BlogPost.objects.published(
                                     for_user=request.user).select_related().filter(user=request.user)
    """
        For now considering blog_posts as a list.
        Going forward we will restrict the #blogposts to be one per user therefore fetching the first element only is sufficient.
        Remove this loop then.
    """
    blog_post = None
    if blog_posts:
        blog_post = blog_posts[0]   
    if (actionObject.actor.__class__.__name__ == "User" and actionObject.actor == request.user) or (actionObject.actor.__class__.__name__ == "BlogPost" and blog_post and actionObject.actor == blog_post):
        """
            Action can be subaction of shared actions.
            Find'em and kill.
        """
        pActionObect = models.Action.objects.all().filter(target_object_id=actionObject.pk)
        if pActionObect is not None:
            for aObject in pActionObect:
                if aObject.verb == settings.SHARE_VERB:
                    aObject.delete()

        """
            If target is generic post, delete it along with feed.
            We do not use type method and not isinstance as BroadcastWish & BroadcastDeal models 
            inherit from GenericWish and will pass the check.
        """
        if actionObject.target and type(actionObject.target) == GenericWish:
            object_instance = actionObject.target
            content_type_id = ContentType.objects.get_for_model(object_instance).pk
            deleteObject(request, content_type_id, object_instance.pk)

        """
        now delete the action
        """
        actionObject.delete()

        return HttpResponse(simplejson.dumps(dict(success=True)))
    else:
        return json_error_response('Unauthorized operation!! request cannot be completed')

def get_broadcasters_info(request, content_type_id, object_id):
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    object = get_object_or_404(ctype.model_class(), pk=object_id)
    broadcasters = Action.objects.get_broadcasters(object)
    unique_broadcasters = list(set(broadcasters['users']))

    return render_to_response("actstream/broadcasters.html", {
        "broadcasters": unique_broadcasters,
    }, context_instance=RequestContext(request))

def get_broadcasters_chunk_info(request, content_type_id, object_id, sIndex=0, lIndex=0):
    s = (int)(""+sIndex)
    l = (int)(""+lIndex)
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    object = get_object_or_404(ctype.model_class(), pk=object_id)
    broadcasters = Action.objects.get_broadcasters_chunk(object, s, l)
    template = "actstream/broadcasters.html"

    if s == 0:
        data_href = reverse('get_broadcasters_chunk_info', kwargs={ 'content_type_id':content_type_id,
                                                                    'object_id':object_id,
                                                                    'sIndex':0,
                                                                    'lIndex': settings.MIN_BROADCASTERS_CHUNK})
        return render_to_response(template, {
            'broadcasters': broadcasters,
            'is_incremental': False,
            'data_href':data_href,
            'data_chunk':settings.MIN_BROADCASTERS_CHUNK
        }, context_instance=RequestContext(request))

    return render_to_response(template, {
        "broadcasters": broadcasters,
    }, context_instance=RequestContext(request))

