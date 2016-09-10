from django.conf import settings

if getattr(settings, 'TESTING_PUBLISH', False):
    from django.test import TransactionTestCase

    from publish.models import FlatPage

    class TestPublishableManager(TransactionTestCase):

        def setUp(self):
            super(TransactionTestCase, self).setUp()
            self.flat_page1 = FlatPage.objects.create(url='/url1/', title='title 1', enable_comments=False, registration_required=False)
            self.flat_page2 = FlatPage.objects.create(url='/url2/', title='title 2', enable_comments=False, registration_required=False)

        def test_all(self):
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.all()))

            # publishing will produce extra copies
            self.flat_page1.publish()
            self.failUnlessEqual(3, FlatPage.objects.count())

            self.flat_page2.publish()
            self.failUnlessEqual(4, FlatPage.objects.count())

        def test_changed(self):
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.changed()))

            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page2], list(FlatPage.objects.changed()))

            self.flat_page2.publish()
            self.failUnlessEqual([], list(FlatPage.objects.changed()))

        def test_draft(self):
            # draft should stay the same pretty much always
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))

            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))

            self.flat_page2.publish()
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))

            self.flat_page2.delete()
            self.failUnlessEqual([self.flat_page1], list(FlatPage.objects.draft()))

        def test_published(self):
            self.failUnlessEqual([], list(FlatPage.objects.published()))

            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page1.public], list(FlatPage.objects.published()))

            self.flat_page2.publish()
            self.failUnlessEqual([self.flat_page1.public, self.flat_page2.public], list(FlatPage.objects.published()))

        def test_deleted(self):
            self.failUnlessEqual([], list(FlatPage.objects.deleted()))

            self.flat_page1.publish()
            self.failUnlessEqual([], list(FlatPage.objects.deleted()))

            self.flat_page1.delete()
            self.failUnlessEqual([self.flat_page1], list(FlatPage.objects.deleted()))

        def test_draft_and_deleted(self):
            self.failUnlessEqual(set([self.flat_page1, self.flat_page2]), set(FlatPage.objects.draft_and_deleted()))

            self.flat_page1.publish()
            self.failUnlessEqual(set([self.flat_page1, self.flat_page2]), set(FlatPage.objects.draft_and_deleted()))
            self.failUnlessEqual(set([self.flat_page1, self.flat_page2]), set(FlatPage.objects.draft()))

            self.flat_page1.delete()
            self.failUnlessEqual(set([self.flat_page1, self.flat_page2]), set(FlatPage.objects.draft_and_deleted()))
            self.failUnlessEqual([self.flat_page2], list(FlatPage.objects.draft()))

        def test_delete(self):
            # delete is overriden, so it marks the public instances
            self.flat_page1.publish()
            public1 = self.flat_page1.public

            FlatPage.objects.draft().delete()

            self.failUnlessEqual([], list(FlatPage.objects.draft()))
            self.failUnlessEqual([self.flat_page1], list(FlatPage.objects.deleted()))
            self.failUnlessEqual([public1], list(FlatPage.objects.published()))
            self.failUnlessEqual([self.flat_page1], list(FlatPage.objects.draft_and_deleted()))

        def test_publish(self):
            self.failUnlessEqual([], list(FlatPage.objects.published()))

            FlatPage.objects.draft().publish()

            flat_page1 = FlatPage.objects.get(id=self.flat_page1.id)
            flat_page2 = FlatPage.objects.get(id=self.flat_page2.id)

            self.failUnlessEqual(set([flat_page1.public, flat_page2.public]), set(FlatPage.objects.published()))
