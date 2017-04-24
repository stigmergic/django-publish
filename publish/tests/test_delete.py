from django.conf import settings

if getattr(settings, 'TESTING_PUBLISH', False):
    from django.conf.urls import include, url
    from django.contrib.admin.sites import AdminSite
    from django.core.exceptions import PermissionDenied
    from django.test import TransactionTestCase, RequestFactory

    from publish.actions import delete_selected, undelete_selected
    from publish.admin import PublishableAdmin
    from publish.models import Publishable
    from .models import FlatPage

    class TestDeleteSelected(TransactionTestCase):

        def setUp(self):
            super(TestDeleteSelected, self).setUp()
            self.fp1 = FlatPage.objects.create(url='/fp1', title='FP1', enable_comments=False, registration_required=False)
            self.fp2 = FlatPage.objects.create(url='/fp2', title='FP2', enable_comments=False, registration_required=False)
            self.fp3 = FlatPage.objects.create(url='/fp3', title='FP3', enable_comments=False, registration_required=False)

            self.fp1.publish()
            self.fp2.publish()
            self.fp3.publish()

            self.admin_site = AdminSite('Test Admin')
            self.page_admin = PublishableAdmin(FlatPage, self.admin_site)

            # override urls, so reverse works
            settings.ROOT_URLCONF = [
                url('^admin/', include(self.admin_site.urls)),
            ]

        def test_delete_selected_check_cannot_delete_public(self):
            # delete won't work (via admin) for public instances
            request = None
            try:
                delete_selected(self.page_admin, request, FlatPage.objects.published())
                self.fail()
            except PermissionDenied:
                pass

        def test_delete_selected(self):

            class user(object):
                @classmethod
                def has_perm(cls, *arg):
                    return True

                @classmethod
                def get_and_delete_messages(cls):
                    return []

                @classmethod
                def is_active(cls, *arg):
                    return True

                @classmethod
                def is_staff(cls, *arg):
                    return True

            rf = RequestFactory()
            dummy_request = rf.request()
            dummy_request.POST = {}
            dummy_request.user = user()

            response = delete_selected(self.page_admin, dummy_request, FlatPage.objects.draft())
            self.failUnless(response is not None)

    class TestUndeleteSelected(TransactionTestCase):

        def setUp(self):
            super(TestUndeleteSelected, self).setUp()
            self.fp1 = FlatPage.objects.create(url='/fp1', title='FP1', enable_comments=False, registration_required=False)

            self.fp1.publish()

            self.admin_site = AdminSite('Test Admin')
            self.page_admin = PublishableAdmin(FlatPage, self.admin_site)

        def test_undelete_selected(self):

            class user(object):
                @classmethod
                def has_perm(cls, *arg):
                    return True

            rf = RequestFactory()
            dummy_request = rf.request()
            dummy_request.user = user()

            self.fp1.delete()
            self.failUnlessEqual(Publishable.PUBLISH_DELETE, self.fp1.publish_state)

            response = undelete_selected(self.page_admin, dummy_request, FlatPage.objects.deleted())
            self.failUnless(response is None)

            # publish state should no longer be delete
            fp1 = FlatPage.objects.get(pk=self.fp1.pk)
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, fp1.publish_state)

        def test_undelete_selected_no_permission(self):

            class user(object):
                @classmethod
                def has_perm(cls, *arg):
                    return False

            rf = RequestFactory()
            dummy_request = rf.request()
            dummy_request.user = user()

            self.fp1.delete()
            self.failUnlessEqual(Publishable.PUBLISH_DELETE, self.fp1.publish_state)

            try:
                undelete_selected(self.page_admin, dummy_request, FlatPage.objects.deleted())
                self.fail()
            except PermissionDenied:
                pass
