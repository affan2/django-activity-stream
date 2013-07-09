from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import HttpResponseRedirect, HttpResponse

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt
from django.utils import simplejson

from actstream import actions, models
from actstream.models import Follow
from django.core.cache import cache
from actstream import action
from django.utils.translation import ugettext_lazy as _
from mezzanine.blog.models import BlogPost
from actstream.models import Action
from follow.models import Follow as _Follow

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
        prevFollowActions = Action.objects.all().filter(actor_content_type=ctype, actor_object_id=object_id,verb=u'started following', target_content_type=target_content_type, target_object_id = followedActor.pk ).order_by('-pk')
        followAction = None
        if prevFollowActions:
            followAction =  prevFollowActions[0]
        if followAction:
            stream = followedActor.actor_actions.public(timestamp__gte = followAction.timestamp)
            activity = activity | stream

        if not isinstance(followedActor, User):
            _follow = _Follow.objects.get_follows(followedActor)
            if _follow:     
                follow = _follow.get(user=actor)
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


def actstream_following_subset(request, content_type_id, object_id, sIndex, lIndex):
    
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)

    activity = cache.get(actor.username)
    if activity is None: 
        activity = actor.actor_actions.public()

        for followedActor in Follow.objects.following(user=actor):
            target_content_type = ContentType.objects.get_for_model(followedActor)
            prevFollowActions = Action.objects.all().filter(actor_content_type=ctype, actor_object_id=object_id,verb=u'started following', target_content_type=target_content_type, target_object_id = followedActor.pk ).order_by('-pk')
            followAction = None
            if prevFollowActions:
                followAction =  prevFollowActions[0]
            if followAction:
                stream = followedActor.actor_actions.public(timestamp__gte = followAction.timestamp)
                activity = activity | stream 
            if not isinstance(followedActor, User):           
                _follow = _Follow.objects.get_follows(followedActor)
                if _follow:     
                    follow = _follow.get(user=actor)
                    if follow:        
                        stream = models.action_object_stream(followedActor, timestamp__gte = follow.datetime )
                        activity = activity | stream 
                        stream = models.target_stream(followedActor, timestamp__gte = follow.datetime )
                        activity = activity | stream

        activity =  activity.order_by('-timestamp')  
        cache.set(actor.username, activity)

    #else:
    #    return HttpResponse(simplejson.dumps(dict(success=False,
    #                                          error_message="heyyy")))
    #activity =  sorted(activity, key=operator.attrgetter('timestamp'), reverse=True)

    s = (int)(""+sIndex)
    l = (int)(""+lIndex)
    activity = activity[s:l]
    return render_to_response(('actstream/actor_feed.html', 'activity/actor_feed.html'), {
       'action_list': activity, 'actor': actor,
       'ctype': ctype, 'sIndex':s
    }, context_instance=RequestContext(request))

def actstream_rebuild_cache(request, content_type_id, object_id):
    from itertools import chain
    import operator    
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)
    activity = actor.actor_actions.public()

    for followedActor in Follow.objects.following(user=actor):
        target_content_type = ContentType.objects.get_for_model(followedActor)
        prevFollowActions = Action.objects.all().filter(actor_content_type=ctype, actor_object_id=object_id,verb=u'started following', target_content_type=target_content_type, target_object_id = followedActor.pk ).order_by('-pk')
        followAction = None
        if prevFollowActions:
            followAction =  prevFollowActions[0]
        if followAction:
            stream = followedActor.actor_actions.public(timestamp__gte = followAction.timestamp)
            activity = activity | stream
        if not isinstance(followedActor, User):
            _follow = _Follow.objects.get_follows(followedActor)
            if _follow:     
                follow = _follow.get(user=actor)
                if follow:        
                    stream = models.action_object_stream(followedActor, timestamp__gte = follow.datetime )
                    activity = activity | stream 
                    stream = models.target_stream(followedActor, timestamp__gte = follow.datetime )
                    activity = activity | stream
    activity =  activity.order_by('-timestamp')
    cache.set(actor.username, activity)
    return HttpResponse(simplejson.dumps(dict(success=True, message="Cache Updated")))

def actstream_actor_rebuild_cache(request, content_type_id, object_id):
    from itertools import chain
    import operator    
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)
    activity = models.actor_stream(actor).order_by('-timestamp')
    cache.set(actor.username+"perso", activity)
    return HttpResponse(simplejson.dumps(dict(success=True, message="Cache Updated")))

def actstream_update_activity(request, content_type_id, object_id): 
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)
    activity = actor.actor_actions.public()

    for followedActor in Follow.objects.following(user=actor):
        target_content_type = ContentType.objects.get_for_model(followedActor)
        prevFollowActions = Action.objects.all().filter(actor_content_type=ctype, actor_object_id=object_id,verb=u'started following', target_content_type=target_content_type, target_object_id = followedActor.pk ).order_by('-pk')
        followAction = None
        if prevFollowActions:
            followAction =  prevFollowActions[0]
        if followAction:
            stream = followedActor.actor_actions.public(timestamp__gte = followAction.timestamp)
            activity = activity | stream
        
        if not isinstance(followedActor, User):
            _follow = _Follow.objects.get_follows(followedActor)
            if _follow:     
                follow = _follow.get(user=actor)
                if follow:        
                    stream = models.action_object_stream(followedActor, timestamp__gte = follow.datetime )
                    activity = activity | stream 
                    stream = models.target_stream(followedActor, timestamp__gte = follow.datetime )
                    activity = activity | stream
    activity =  activity.order_by('-timestamp')

    lastActivity = cache.get(actor.username)
    oldIndex = 0
    lastActivityCount = 0
    if lastActivity:
        lastActivityCount = lastActivity.count()
    if activity:
        oldIndex = activity.count() - lastActivityCount

    cache.set(actor.username, activity)
  
    activity = activity[0:oldIndex]

    return render_to_response(('actstream/actor_feed.html', 'activity/actor_feed.html'), {
       'action_list': activity, 'actor': actor,
       'ctype': ctype, 'sIndex':lastActivityCount + 1
    }, context_instance=RequestContext(request))

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

def actstream_actor_subset(request, content_type_id, object_id, sIndex, lIndex):
    """
    ``Actor`` focused activity stream for actor defined by ``content_type_id``,
    ``object_id``.
    """
    import operator

    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)

    activity = cache.get(actor.username+"perso")

    if activity is None: 
        activity = models.actor_stream(actor).order_by('-timestamp') 
        cache.set(actor.username+"perso", activity)
        #return json_error_response("hellooo")
    s = (int)(""+sIndex)
    l = (int)(""+lIndex)

    activity = activity[s:l]

    return render_to_response(('actstream/actor_feed.html', 'activity/actor_feed.html'), {
       'action_list': activity, 'actor': actor,
       'ctype': ctype, 'sIndex':s
    }, context_instance=RequestContext(request))


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
    action.send(request.user, verb=_('shared'), target=actionObject)
    if request.is_ajax():
        return HttpResponse('ok') 
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
                if aObject.verb == _('shared'):
                    aObject.delete()
        """
        now delete the action
        """
        actionObject.delete()

        return HttpResponse('ok')
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

