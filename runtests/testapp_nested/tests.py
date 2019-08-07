from django.core.exceptions import ImproperlyConfigured

from actstream.registry import register, registry
from actstream.tests.base import ActivityBaseTestCase

from .models import my_model
from ..notinstalled.models import NotInstalledModel


class TestAppNestedTests(ActivityBaseTestCase):
    def test_registration(self):
        self.assertIn(my_model.NestedModel, registry)

    def test_not_installed(self):
        self.assertRaises(ImproperlyConfigured, register, NotInstalledModel)
