from django.conf import settings

if getattr(settings, 'TESTING_PUBLISH', False):
    from django.test import TransactionTestCase

    from publish.models import Publishable, UnpublishException, PublishException
    from publish.utils import NestedSet
    from .models import FlatPage

    class TestBasicPublishable(TransactionTestCase):

        def setUp(self):
            super(TestBasicPublishable, self).setUp()
            self.flat_page = FlatPage(url='/my-page', title='my page',
                                      content='here is some content',
                                      enable_comments=False,
                                      registration_required=True)

        def test_get_public_absolute_url(self):
            self.failUnlessEqual('/my-page*', self.flat_page.get_absolute_url())
            # public absolute url doesn't exist until published
            self.assertTrue(self.flat_page.get_public_absolute_url() is None)
            self.flat_page.save()
            self.flat_page.publish()
            self.failUnlessEqual('/my-page', self.flat_page.get_public_absolute_url())

        def test_save_marks_changed(self):
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save(mark_changed=False)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)

        def test_publish_excludes_fields(self):
            self.flat_page.save()
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failIfEqual(self.flat_page.id, self.flat_page.public.id)
            self.failUnless(self.flat_page.public.is_public)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.public.publish_state)

        def test_publish_check_is_not_public(self):
            try:
                self.flat_page.is_public = True
                self.flat_page.publish()
                self.fail("Should not be able to publish public models")
            except PublishException:
                pass

        def test_publish_check_has_id(self):
            try:
                self.flat_page.publish()
                self.fail("Should not be able to publish unsaved models")
            except PublishException:
                pass

        def test_publish_simple_fields(self):
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)
            self.failIf(self.flat_page.public)  # should not be a public version yet

            self.flat_page.publish()
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.failUnless(self.flat_page.public)

            for field in 'url', 'title', 'content', 'enable_comments', 'registration_required':
                self.failUnlessEqual(getattr(self.flat_page, field), getattr(self.flat_page.public, field))

        def test_published_simple_field_repeated(self):
            self.flat_page.save()
            self.flat_page.publish()

            public = self.flat_page.public
            self.failUnless(public)

            self.flat_page.title = 'New Title'
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)

            self.failUnlessEqual(public, self.flat_page.public)
            self.failIfEqual(public.title, self.flat_page.title)

            self.flat_page.publish()
            self.failUnlessEqual(public, self.flat_page.public)
            self.failUnlessEqual(public.title, self.flat_page.title)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)

        def test_publish_records_published(self):
            all_published = NestedSet()
            self.flat_page.save()
            self.flat_page.publish(all_published=all_published)
            self.failUnlessEqual(1, len(all_published))
            self.failUnless(self.flat_page in all_published)
            self.failUnless(self.flat_page.public)

        def test_publish_dryrun(self):
            all_published = NestedSet()
            self.flat_page.save()
            self.flat_page.publish(dry_run=True, all_published=all_published)
            self.failUnlessEqual(1, len(all_published))
            self.failUnless(self.flat_page in all_published)
            self.failIf(self.flat_page.public)
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)

        def test_delete_after_publish(self):
            self.flat_page.save()
            self.flat_page.publish()
            public = self.flat_page.public
            self.failUnless(public)

            self.flat_page.delete()
            self.failUnlessEqual(Publishable.PUBLISH_DELETE, self.flat_page.publish_state)

            self.failUnlessEqual(set([self.flat_page, self.flat_page.public]), set(FlatPage.objects.all()))

        def test_delete_before_publish(self):
            self.flat_page.save()
            self.flat_page.delete()
            self.failUnlessEqual([], list(FlatPage.objects.all()))

        def test_publish_deletions(self):
            self.flat_page.save()
            self.flat_page.publish()
            public = self.flat_page.public

            self.failUnlessEqual(set([self.flat_page, public]), set(FlatPage.objects.all()))

            self.flat_page.delete()
            self.failUnlessEqual(set([self.flat_page, public]), set(FlatPage.objects.all()))

            self.flat_page.publish()
            self.failUnlessEqual([], list(FlatPage.objects.all()))

        def test_publish_deletions_checks_all_published(self):
            # make sure publish_deletions looks at all_published arg
            # to see if we need to actually publish the deletion
            self.flat_page.save()
            self.flat_page.publish()
            public = self.flat_page.public

            self.flat_page.delete()

            self.failUnlessEqual(set([self.flat_page, public]), set(FlatPage.objects.all()))

            # this should effectively stop the deletion happening
            all_published = NestedSet()
            all_published.add(self.flat_page)

            self.flat_page.publish(all_published=all_published)
            self.failUnlessEqual(set([self.flat_page, public]), set(FlatPage.objects.all()))

    class TestBasicUnpublishable(TransactionTestCase):

        def setUp(self):
            super(TestBasicUnpublishable, self).setUp()
            self.flat_page = FlatPage(url='/my-page', title='my page',
                                      content='here is some content',
                                      enable_comments=False,
                                      registration_required=True)

        def test_unpublish_dry_run(self):
            with self.assertRaises(UnpublishException):
                self.flat_page.unpublish(dry_run=True)

            self.flat_page.save()

            with self.assertRaises(UnpublishException):
                self.flat_page.is_public = True
                self.flat_page.unpublish(dry_run=True)

            self.flat_page.is_public = False
            self.flat_page.publish()
            self.failUnlessEqual(self.flat_page.unpublish(dry_run=True), self.flat_page.public)

        def test_unpublish(self):
            self.flat_page.save()
            published_page = self.flat_page.publish()

            _draft_page = FlatPage.objects.get(pk=self.flat_page.pk)
            _published_page = FlatPage.objects.get(pk=published_page.pk)

            self.failUnlessEqual(_draft_page.public.pk, _published_page.pk)

            _draft_page.unpublish()

            _published_page = FlatPage.objects.filter(pk=published_page.pk)
            self.failUnlessEqual(0, len(_published_page))
            self.failUnlessEqual(None, _draft_page.public)
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, _draft_page.publish_state)
