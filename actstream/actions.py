import datetime

from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from itertools import chain

from actstream.exceptions import check_actionable_model
from actstream import settings
from django.conf import settings as _settings
try:
    from django.utils import timezone
    now = timezone.now
except ImportError:
    now = datetime.datetime.now


def follow(user, obj, send_action=True, actor_only=True):
    """
    Creates a relationship allowing the object's activities to appear in the
    user's stream.

    Returns the created ``Follow`` instance.

    If ``send_action`` is ``True`` (the default) then a
    ``<user> started following <object>`` action signal is sent.

    If ``actor_only`` is ``True`` (the default) then only actions where the
    object is the actor will appear in the user's activity stream. Set to
    ``False`` to also include actions where this object is the action_object or
    the target.

    Example::

        follow(request.user, group, actor_only=False)
    """
    from actstream.models import Follow, action
    from people.tasks import task_notice

    check_actionable_model(obj)
    follow, created = Follow.objects.get_or_create(
        user=user,
        object_id=obj.pk,
        content_type=ContentType.objects.get_for_model(obj),
        actor_only=actor_only,
        site_id=_settings.SITE_ID,
    )
    if send_action and created:
        action.send(
            user,
            verb=_settings.FOLLOW_VERB,
            target=obj,
            batch_time_minutes=30,
            is_batchable=True
        )
        recipients = [obj]
        if obj.__class__.__name__ == 'Company':
            admins = obj.admins.all()
            recipients = set(chain(
                [obj.admin_primary] if obj.admin_primary and not obj.admin_primary.is_staff else [],
                admins
            ))

        if not obj.__class__.__name__ == 'Post':
            task_notice.delay(
                recipients,
                "follower",
                {'target': obj},
                sender=user
            )

    return follow


def unfollow(user, obj, send_action=False):
    """
    Removes a "follow" relationship.

    Set ``send_action`` to ``True`` (``False is default) to also send a
    ``<user> stopped following <object>`` action signal.

    Example::

        unfollow(request.user, other_user)
    """
    from actstream.models import Follow, action

    check_actionable_model(obj)
    Follow.objects.filter(user=user, object_id=obj.pk,
        content_type=ContentType.objects.get_for_model(obj)).delete()
    if send_action:
        action.send(user, verb=_settings.UNFOLLOW_VERB, target=obj)


def is_following(user, obj):
    """
    Checks if a "follow" relationship exists.

    Returns True if exists, False otherwise.

    Example::

        is_following(request.user, group)
    """
    from actstream.models import Follow

    check_actionable_model(obj)
    return bool(Follow.objects.filter(
        user=user,
        object_id=obj.pk,
        content_type=ContentType.objects.get_for_model(obj),
        site_id=_settings.SITE_ID
    ).count())


def action_handler(verb, **kwargs):
    """
    Handler function to create Action instance upon action signal call.
    """
    from actstream.models import Action

    kwargs.pop('signal', None)
    actor = kwargs.pop('sender')
    check_actionable_model(actor)
    if check_action_exists(actor, verb, **kwargs):
        newaction = Action(
            actor_content_type=ContentType.objects.get_for_model(actor),
            actor_object_id=actor.pk,
            verb=unicode(verb),
            public=bool(kwargs.pop('public', True)),
            description=kwargs.pop('description', None),
            timestamp=kwargs.pop('timestamp', now()),
            batch_time_minutes=kwargs.pop('batch_time_minutes', 30),
            is_batchable=kwargs.pop('is_batchable', False),
            site_id=_settings.SITE_ID
        )

        for opt in ('target', 'action_object'):
            obj = kwargs.pop(opt, None)
            if not obj is None:
                check_actionable_model(obj)
                setattr(newaction, '%s_object_id' % opt, obj.pk)
                setattr(newaction, '%s_content_type' % opt,
                        ContentType.objects.get_for_model(obj))
        if settings.USE_JSONFIELD and len(kwargs):
            newaction.data = kwargs
        newaction.save()


def check_action_exists(actor, verb, **kwargs):
    from actstream.models import Action

    filters = {
        'actor_content_type': ContentType.objects.get_for_model(actor),
        'actor_object_id': actor.pk,
        'verb': unicode(verb),
        'state': 1,
        'timestamp_date': kwargs.get('timestamp', now()),
        'site_id': _settings.SITE_ID,
    }
    for opt in ('target', 'action_object'):
        obj = kwargs.pop(opt, None)
        if not obj is None:
            check_actionable_model(obj)
            filters.update({'%s_object_id' % opt: obj.pk})
            filters.update({'%s_content_type' % opt: ContentType.objects.get_for_model(obj)})

    try:
        action = Action.objects.get(**filters)

        action.timestamp = kwargs.get('timestamp', now())
        action.save()

    except Action.DoesNotExist:
        return True

    except Action.MultipleObjectsReturned:
        actions = Action.objects.filter(**filters).order_by('-id')
        i = 1
        for action in actions:
            if i == 1:
                action.timestamp = kwargs.get('timestamp', now())
                action.save()
                i += 1
            else:
                action.delete()

    return False


