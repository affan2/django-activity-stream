from actstream.models import Follow, Action
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.template import Variable, Library, Node, TemplateSyntaxError, resolve_variable, VariableDoesNotExist
from django.template.base import TemplateDoesNotExist
from django.template.loader import render_to_string, find_template
from django.core.cache import cache
import itertools


register = Library()


def _is_following_helper(context, actor):
    return Follow.objects.is_following(context.get('user'), actor)


class DisplayActivityFollowUrl(Node):
    def __init__(self, actor, actor_only=True):
        self.actor = Variable(actor)
        self.actor_only = actor_only

    def render(self, context):
        actor_instance = self.actor.resolve(context)
        content_type = ContentType.objects.get_for_model(actor_instance).pk
        if Follow.objects.is_following(context.get('user'), actor_instance):
            return reverse('actstream_unfollow', kwargs={
                'content_type_id': content_type, 'object_id': actor_instance.pk})
        if self.actor_only:
            return reverse('actstream_follow', kwargs={
                'content_type_id': content_type, 'object_id': actor_instance.pk})
        return reverse('actstream_follow_all', kwargs={
            'content_type_id': content_type, 'object_id': actor_instance.pk})


class DisplayActivityActorUrl(Node):
    def __init__(self, actor):
        self.actor = Variable(actor)

    def render(self, context):
        actor_instance = self.actor.resolve(context)
        content_type = ContentType.objects.get_for_model(actor_instance).pk
        return reverse('actstream_actor', kwargs={
            'content_type_id': content_type, 'object_id': actor_instance.pk})

class DisplayFollowerActivityUrl(Node):
    def __init__(self, actor):
        self.actor = Variable(actor)

    def render(self, context):
        actor_instance = self.actor.resolve(context)
        content_type = ContentType.objects.get_for_model(actor_instance).pk
        return reverse('actstream_following', kwargs={
            'content_type_id': content_type, 'object_id': actor_instance.pk})


class AsNode(Node):
    """
    Base template Node class for template tags that takes a predefined number
    of arguments, ending in an optional 'as var' section.
    """
    args_count = 3

    @classmethod
    def handle_token(cls, parser, token):
        """
        Class method to parse and return a Node.
        """
        bits = token.split_contents()
        args_count = len(bits) - 1
        if args_count >= 2 and bits[-2] == 'as':
            as_var = bits[-1]
            args_count -= 2
        else:
            as_var = None
        if args_count != cls.args_count:
            arg_list = ' '.join(['[arg]' * cls.args_count])
            raise TemplateSyntaxError("Accepted formats {%% %(tagname)s "
                "%(args)s %%} or {%% %(tagname)s %(args)s as [var] %%}" %
                {'tagname': bits[0], 'args': arg_list})
        args = [parser.compile_filter(token) for token in
            bits[1:args_count + 1]]
        return cls(args, varname=as_var)

    def __init__(self, args, varname=None):
        self.args = args
        self.varname = varname

    def render(self, context):
        result = self.render_result(context)
        if self.varname is not None:
            context[self.varname] = result
            return ''
        return result

    def render_result(self, context):
        raise NotImplementedError("Must be implemented by a subclass")


class DisplayAction(AsNode):

    def render_result(self, context):
        action_instance = self.args[0].resolve(context)
        templates = [
            'actstream/%s/action.html' % action_instance.verb.replace(' ', '_'),
            'actstream/action.html',
            'activity/%s/action.html' % action_instance.verb.replace(' ', '_'),
            'activity/action.html',
        ]
        return render_to_string(templates, {'action': action_instance},
            context)

class RenderAction(Node):
    def __init__(self, action):
        self.action = Variable(action)

    def render(self, context):
        action_instance = self.action.resolve(context)
        templates = [
            'actstream/%s/action.html' % action_instance.verb.replace(' ', '_'),
            'actstream/action.html',
            'activity/%s/action.html' % action_instance.verb.replace(' ', '_'),
            'activity/action.html',
        ]
        return render_to_string(templates, {'action': action_instance},
            context)

class DisplayFollowerActivitySubsetUrl(AsNode):

    def render_result(self, context):
        actor_instance = self.args[0].resolve(context)
        sIndex = self.args[1].resolve(context)
        lIndex = self.args[2].resolve(context)
        content_type = ContentType.objects.get_for_model(actor_instance).pk
        
        return reverse('actstream_following_subset', kwargs={
            'content_type_id': content_type, 'object_id': actor_instance.pk, 'sIndex':sIndex, 'lIndex':lIndex})

class ShareActivityUrl(Node):
    def __init__(self, action):
        self.action = Variable(action)

    def render(self, context):
        action_instance = self.action.resolve(context)
        return reverse('shareAction', kwargs={
            'action_id':action_instance.pk})

class ShareActivityCount(Node):
    def __init__(self, action, context_var):
        self.action = Variable(action)
        self.context_var = context_var

    def render(self, context):
        action_instance = self.action.resolve(context)
        target_content_type = ContentType.objects.get_for_model(action_instance)
        context[self.context_var] = Action.objects.filter(verb='shared', target_content_type=target_content_type, target_object_id = action_instance.pk).count()
        return  ''

class CanShareActivity(Node):
    def __init__(self, action, context_var):
        self.action = Variable(action)
        self.context_var = context_var

    def render(self, context):
        user = context['request'].user
        action_instance = self.action.resolve(context)
        actor_content_type = ContentType.objects.get_for_model(user)
        target_content_type = ContentType.objects.get_for_model(action_instance)
        alreadyShared = Action.objects.filter(actor_content_type=actor_content_type,actor_object_id=user._get_pk_val(), verb='shared', target_content_type=target_content_type, target_object_id = action_instance.pk).count()
        if alreadyShared == 0:
            if action_instance.verb != "shared" and action_instance.actor != user:
                context[self.context_var] = 1  
            else:
                context[self.context_var] = 0
        else:
            context[self.context_var] = 0
        return ''


class DeleteActivityUrl(Node):
    def __init__(self, action):
        self.action = Variable(action)

    def render(self, context):
        action_instance = self.action.resolve(context)
        return reverse('deleteAction', kwargs={
            'action_id':action_instance.pk})

class DisplayActivitySubsetActorUrl(AsNode):
    def render_result(self, context):
        actor_instance = self.args[0].resolve(context)
        sIndex = self.args[1].resolve(context)
        lIndex = self.args[2].resolve(context)
        content_type = ContentType.objects.get_for_model(actor_instance).pk
        
        return reverse('actstream_actor_subset', kwargs={
            'content_type_id': content_type, 'object_id': actor_instance.pk, 'sIndex':sIndex, 'lIndex':lIndex})


class FollowerActivityRebuildCache(Node):
    def __init__(self, actor):
        self.actor = Variable(actor)

    def render(self, context):
        actor_instance = self.actor.resolve(context)
        content_type = ContentType.objects.get_for_model(actor_instance).pk
        return reverse('actstream_rebuild_cache', kwargs={'content_type_id': content_type, 'object_id': actor_instance.pk })

class FollowerActivityActorRebuildCache(Node):
    def __init__(self, actor):
        self.actor = Variable(actor)

    def render(self, context):
        actor_instance = self.actor.resolve(context)
        content_type = ContentType.objects.get_for_model(actor_instance).pk
        return reverse('actstream_actor_rebuild_cache', kwargs={'content_type_id': content_type, 'object_id': actor_instance.pk })

class FollowerActivityDynamicUpdate(Node):
    def __init__(self, actor):
        self.actor = Variable(actor)

    def render(self, context):
        actor_instance = self.actor.resolve(context)
        content_type = ContentType.objects.get_for_model(actor_instance).pk
        return reverse('actstream_update_activity', kwargs={'content_type_id': content_type, 'object_id': actor_instance.pk })

class BroadcastersForObjectNode(Node):
    def __init__(self, object, context_var):
        self.object = object
        self.context_var = context_var

    def render(self, context):
        try:
            object = resolve_variable(self.object, context)
            content_type = ContentType.objects.get_for_model(object).pk
        except VariableDoesNotExist:
            return ''
        context[self.context_var] = reverse('get_broadcasters_info', kwargs={'content_type_id': content_type, 'object_id': object.pk })
        return ''

def display_action(parser, token):
    """
    Renders the template for the action description

    Example::

        {% display_action action %}
    """
    return DisplayAction.handle_token(parser, token)

def render_action(parser, token):
    bits = token.split_contents()
    return RenderAction(bits[1])


def is_following(user, actor):
    """
    Returns true if the given user is following the actor

    Example::

        {% if request.user|is_following:another_user %}
            You are already following {{ another_user }}
        {% endif %}
    """
    return Follow.objects.is_following(user, actor)


def follow_url(parser, token):
    """
    Renders the URL of the follow view for a particular actor instance

    Example::

        <a href="{% follow_url other_user %}">
            {% if request.user|is_following:other_user %}
                stop following
            {% else %}
                follow
            {% endif %}
        </a>
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("Accepted format {% follow_url [instance] %}")
    else:
        return DisplayActivityFollowUrl(bits[1])


def follow_all_url(parser, token):
    """
    Renders the URL to follow an object as both actor and target

    Example::

        <a href="{% follow_all_url other_user %}">
            {% if request.user|is_following:other_user %}
                stop following
            {% else %}
                follow
            {% endif %}
        </a>
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("Accepted format {% follow_all_url [instance] %}")
    else:
        return DisplayActivityFollowUrl(bits[1], actor_only=False)


def actor_url(parser, token):
    """
    Renders the URL for a particular actor instance

    Example::

        <a href="{% actor_url request.user %}">View your actions</a>
        <a href="{% actor_url another_user %}">{{ another_user }}'s actions</a>

    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("Accepted format "
                                  "{% actor_url [actor_instance] %}")
    else:
        return DisplayActivityActorUrl(*bits[1:])

def following_feed_url(parser, token):
    """
    Renders the URL for a particular actor instance

    Example::

        <a href="{% actor_url request.user %}">View your actions</a>
        <a href="{% actor_url another_user %}">{{ another_user }}'s actions</a>

    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("Accepted format "
                                  "{% follower_feed_url [actor_instance] %}")
    else:
        return DisplayFollowerActivityUrl(*bits[1:])

def following_feedsubset_url(parser, token):
    """
    Renders the URL for a particular actor instance

    Example::

        <a href="{% actor_url request.user %}">View your actions</a>
        <a href="{% actor_url another_user %}">{{ another_user }}'s actions</a>

    """
    bits = token.split_contents()
    if len(bits) != 6:
        raise TemplateSyntaxError("Accepted format "
                                  "{% follower_feed_url [actor_instance] %}")
    else:
        return DisplayFollowerActivitySubsetUrl.handle_token(parser, token)

def share_action_url(parser, token):
    bits = token.split_contents()
    return ShareActivityUrl(*bits[1:])

def get_share_count(parser, token):
    bits = token.contents.split()
    if len(bits) != 4:
        raise TemplateSyntaxError("'%s' tag takes exactly three arguments" % bits[0])
    if bits[2] != 'as':
        raise TemplateSyntaxError("second argument to '%s' tag must be 'as'" % bits[0])
    return ShareActivityCount(bits[1], bits[3])

def can_share_action(parser, token):
    bits = token.contents.split()
    if len(bits) != 4:
        raise TemplateSyntaxError("'%s' tag takes exactly three arguments" % bits[0])
    if bits[2] != 'as':
        raise TemplateSyntaxError("second argument to '%s' tag must be 'as'" % bits[0])
    return CanShareActivity(bits[1], bits[3])

def delete_action_url(parser, token):
    bits = token.split_contents()
    return DeleteActivityUrl(*bits[1:])

def actor_url_subset(parser, token):
    """
    Renders the URL for a particular actor instance

    Example::

        {% actor_url_subset request.user sindex lindex as feed%}"

    """
    bits = token.split_contents()
    if len(bits) != 6:
        raise TemplateSyntaxError("Accepted format "
                                  "{% actor_url_subset request.user sindex lindex as feed %}")
    else:
        return DisplayActivitySubsetActorUrl.handle_token(parser, token)

def activity_refresh_cache(parser, token):
    """
    Refreshes the user activity feed cache

    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("Accepted format "
                                  "{% activity_refresh_cache [actor_instance] %}")
    else:
        return FollowerActivityRebuildCache(*bits[1:])

def activity_actor_refresh_cache(parser, token):
    """
    Refreshes the user activity feed cache

    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("Accepted format "
                                  "{% activity_actor_refresh_cache [actor_instance] %}")
    else:
        return FollowerActivityActorRebuildCache(*bits[1:])

def activity_dynamic_update(parser, token):
    """
    Refreshes the user activity feed cache

    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("Accepted format "
                                  "{% activity_dynamic_update [actor_instance] %}")
    else:
        return FollowerActivityDynamicUpdate(*bits[1:])

def do_broadcasters_for_action(parser, token):
    """
    Retrieves the list of broadcasters for an action and stores them in a context variable which has
    ``broadcasters`` property.

    Example usage::

        {% broadcasters_for_action widget as voters %}
    """
    bits = token.contents.split()
    if len(bits) != 4:
        raise template.TemplateSyntaxError("'%s' tag takes exactly three arguments" % bits[0])
    if bits[2] != 'as':
        raise template.TemplateSyntaxError("second argument to '%s' tag must be 'as'" % bits[0])
    return BroadcastersForObjectNode(bits[1], bits[3])

def get_class_name(obj):
    return obj.__class__.__name__


@register.inclusion_tag("actstream/render_album.html", takes_context=True)
def render_album(context, album):
    
    context.update({
        "image_list": album.images.all().order_by('-created'),
    })
    return context

@register.filter
def get_value_from_dict(dictionary, key):
    return dictionary.get(key)

def do_get_list_of_batched_action_ids(parser, token):
    """
    Retrieves the list of broadcasters for an action and stores them in a context variable which has
    ``broadcasters`` property.

    Example usage::

        {% do_get_list_of_batched_action_ids as voters %}
    """
    bits = token.contents.split()
    if len(bits) != 3:
        raise template.TemplateSyntaxError("'%s' tag takes exactly two arguments" % bits[0])
    if bits[1] != 'as':
        raise template.TemplateSyntaxError("second argument to '%s' tag must be 'as'" % bits[0])
    return GetListOfBatchedActionIDs(bits[2])

class GetListOfBatchedActionIDs(Node):
    def __init__(self, context_var):
        self.context_var = context_var

    def render(self, context):
        try:
            user = context['request'].user
            action_id_maps = cache.get(user.username+"batched_actions")
            action_id_list = action_id_maps.values()
        except VariableDoesNotExist:
            return ''
        context[self.context_var] = list(itertools.chain(*action_id_list))
        return ''

def do_get_action_target(parser, token):
    """
    Retrieves the list of broadcasters for an action and stores them in a context variable which has
    ``broadcasters`` property.

    Example usage::

        {% do_get_list_of_batched_action_ids as voters %}
    """
    bits = token.contents.split()
    if len(bits) != 4:
        raise TemplateSyntaxError("'%s' tag takes exactly two arguments" % bits[0])
    if bits[2] != 'as':
        raise TemplateSyntaxError("second argument to '%s' tag must be 'as'" % bits[0])
    return GetActionTarget(bits[1],bits[3])

class GetActionTarget(Node):
    def __init__(self, action_id, context_var):
        self.action_id = action_id
        self.context_var = context_var

    def render(self, context):
        try:
            action_id = resolve_variable(self.action_id, context)
            action_object = Action.objects.get(id=action_id)
        except VariableDoesNotExist:
            return ''
        context[self.context_var] = action_object.target
        return ''

def do_get_action_actor(parser, token):
    """
    Retrieves the list of broadcasters for an action and stores them in a context variable which has
    ``broadcasters`` property.

    Example usage::

        {% do_get_list_of_batched_action_ids as voters %}
    """
    bits = token.contents.split()
    if len(bits) != 4:
        raise TemplateSyntaxError("'%s' tag takes exactly two arguments" % bits[0])
    if bits[2] != 'as':
        raise TemplateSyntaxError("second argument to '%s' tag must be 'as'" % bits[0])
    return GetActionActor(bits[1],bits[3])

class GetActionActor(Node):
    def __init__(self, action_id, context_var):
        self.action_id = action_id
        self.context_var = context_var

    def render(self, context):
        try:
            action_id = resolve_variable(self.action_id, context)
            action_object = Action.objects.get(id=action_id)
        except VariableDoesNotExist:
            return ''
        context[self.context_var] = action_object.actor
        return ''


register.filter(is_following)
register.filter(get_class_name)
register.tag(display_action)
register.tag(render_action)
register.tag(follow_url)
register.tag(follow_all_url)
register.tag(actor_url)
register.tag(actor_url_subset)
register.tag(following_feed_url)
register.tag(following_feedsubset_url)
register.tag(activity_refresh_cache)
register.tag(activity_actor_refresh_cache)
register.tag(activity_dynamic_update)
register.tag(get_share_count)
register.tag(share_action_url)
register.tag(delete_action_url)
register.tag(can_share_action)
register.tag('broadcasters_for_action', do_broadcasters_for_action)
register.tag('get_list_of_batched_action_ids', do_get_list_of_batched_action_ids)
register.tag('get_action_target',do_get_action_target)
register.tag('get_action_actor',do_get_action_actor)

@register.filter
def backwards_compatibility_check(template_name):
    backwards = False
    try:
        find_template('actstream/action.html')
    except TemplateDoesNotExist:
        backwards = True
    if backwards:
        template_name = template_name.replace('actstream/', 'activity/')
    return template_name