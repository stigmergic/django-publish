# -*- coding: utf-8 -*-
from django.test.client import RequestFactory
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage


class RequestFactoryMixin(object):

    def build_user(self):
        user, is_created = User.objects.get_or_create(username='chuck_norris', email='chuck_norris@god.com', password='chuck_norris')
        user.is_staff = True
        user.is_superuser = True
        user.save()

        return user

    def build_common_user(self):
        user, is_created = User.objects.get_or_create(username='arthur_dent', email='arthur@dontpanic.com', password='42')
        return user

    def build_get_request(self, url='/', **kwargs):
        rf = RequestFactory()
        request = rf.get(url, **kwargs)
        request.user = self.build_user()
        return request

    def build_post_request(self, data, url='/'):
        rf = RequestFactory()
        request = rf.post(url, data)
        request.user = self.build_user()
        request._dont_enforce_csrf_checks = True

        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        return request
