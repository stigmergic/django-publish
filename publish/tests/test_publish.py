from django.conf import settings

if getattr(settings, 'TESTING_PUBLISH', False):
    from django.test import TransactionTestCase

    from publish.admin import PublishableAdmin
    from publish.filters import PublishableRelatedFieldListFilter
    from publish.models import Publishable, Page, Author, update_pub_date
    from publish.signals import pre_publish, post_publish
    from publish.utils import NestedSet

    class TestPublishFunction(TransactionTestCase):

        def setUp(self):
            super(TestPublishFunction, self).setUp()
            self.page = Page.objects.create(slug='page', title='Page')

        def test_publish_function_invoked(self):
            # check we can override default copy behaviour

            from datetime import datetime

            pub_date = datetime(2000, 1, 1)
            update_pub_date.pub_date = pub_date

            self.failIfEqual(pub_date, self.page.pub_date)

            self.page.publish()
            self.failIfEqual(pub_date, self.page.pub_date)
            self.failUnlessEqual(pub_date, self.page.public.pub_date)

    class TestPublishSignals(TransactionTestCase):

        def setUp(self):
            self.page1 = Page.objects.create(slug='page1', title='page 1')
            self.page2 = Page.objects.create(slug='page2', title='page 2')
            self.child1 = Page.objects.create(parent=self.page1, slug='child1', title='Child 1')
            self.child2 = Page.objects.create(parent=self.page1, slug='child2', title='Child 2')
            self.child3 = Page.objects.create(parent=self.page2, slug='child3', title='Child 3')

            self.failUnlessEqual(5, Page.objects.draft().count())

        def _check_pre_publish(self, queryset):
            pre_published = []

            def pre_publish_handler(sender, instance, **kw):
                pre_published.append(instance)

            pre_publish.connect(pre_publish_handler, sender=Page)

            queryset.draft().publish()

            self.failUnlessEqual(queryset.draft().count(), len(pre_published))
            self.failUnlessEqual(set(queryset.draft()), set(pre_published))

        def test_pre_publish(self):
            # page order shouldn't matter when publishing
            # should always get the right number of signals
            self._check_pre_publish(Page.objects.order_by('id'))
            self._check_pre_publish(Page.objects.order_by('-id'))
            self._check_pre_publish(Page.objects.order_by('?'))

        def _check_post_publish(self, queryset):
            published = []

            def post_publish_handler(sender, instance, **kw):
                published.append(instance)

            post_publish.connect(post_publish_handler, sender=Page)

            queryset.draft().publish()

            self.failUnlessEqual(queryset.draft().count(), len(published))
            self.failUnlessEqual(set(queryset.draft()), set(published))

        def test_post_publish(self):
            self._check_post_publish(Page.objects.order_by('id'))
            self._check_post_publish(Page.objects.order_by('-id'))
            self._check_post_publish(Page.objects.order_by('?'))

        def test_signals_sent_for_followed(self):
            pre_published = []

            def pre_publish_handler(sender, instance, **kw):
                pre_published.append(instance)

            pre_publish.connect(pre_publish_handler, sender=Page)

            published = []

            def post_publish_handler(sender, instance, **kw):
                published.append(instance)

            post_publish.connect(post_publish_handler, sender=Page)

            # publishing just children will also publish it's parent (if needed)
            # which should also fire signals

            self.child1.publish()

            self.failUnlessEqual(set([self.page1, self.child1]), set(pre_published))
            self.failUnlessEqual(set([self.page1, self.child1]), set(published))

        def test_deleted_flag_false_when_publishing_change(self):
            def pre_publish_handler(sender, instance, deleted, **kw):
                self.failIf(deleted)

            pre_publish.connect(pre_publish_handler, sender=Page)

            def post_publish_handler(sender, instance, deleted, **kw):
                self.failIf(deleted)

            post_publish.connect(post_publish_handler, sender=Page)

            self.page1.publish()

        def test_deleted_flag_true_when_publishing_deletion(self):
            self.child1.publish()
            self.child1.public

            self.child1.delete()

            self.failUnlessEqual(Publishable.PUBLISH_DELETE, self.child1.publish_state)

            def pre_publish_handler(sender, instance, deleted, **kw):
                self.failUnless(deleted)

            pre_publish.connect(pre_publish_handler, sender=Page)

            def post_publish_handler(sender, instance, deleted, **kw):
                self.failUnless(deleted)

            post_publish.connect(post_publish_handler, sender=Page)

            self.child1.publish()

    try:
        from django.contrib.admin.filters import FieldListFilter
    except ImportError:
        # pre 1.4
        from django.contrib.admin.filterspecs import FilterSpec

        class FieldListFilter(object):
            @classmethod
            def create(cls, field, request, params, model, model_admin, *arg, **kw):
                return FilterSpec.create(field, request, params, model, model_admin)

    class TestPublishableRelatedFilterSpec(TransactionTestCase):

        def test_overridden_spec(self):
            # make sure the publishable filter spec
            # gets used when we use a publishable field
            class dummy_request(object):
                GET = {}

            spec = FieldListFilter.create(Page._meta.get_field('authors'), dummy_request, {}, Page, PublishableAdmin, None)
            self.failUnless(isinstance(spec, PublishableRelatedFieldListFilter))

        def test_only_draft_shown(self):
            self.author = Author.objects.create(name='author')
            self.author.publish()

            self.failUnless(2, Author.objects.count())

            # make sure the publishable filter spec
            # gets used when we use a publishable field
            class dummy_request(object):
                GET = {}

            spec = FieldListFilter.create(Page._meta.get_field('authors'), dummy_request, {}, Page, PublishableAdmin, None)

            lookup_choices = spec.lookup_choices
            self.failUnlessEqual(1, len(lookup_choices))
            pk, label = lookup_choices[0]
            self.failUnlessEqual(self.author.id, pk)

    class TestOverlappingPublish(TransactionTestCase):

        def setUp(self):
            self.page1 = Page.objects.create(slug='page1', title='page 1')
            self.page2 = Page.objects.create(slug='page2', title='page 2')
            self.child1 = Page.objects.create(parent=self.page1, slug='child1', title='Child 1')
            self.child2 = Page.objects.create(parent=self.page1, slug='child2', title='Child 2')
            self.child3 = Page.objects.create(parent=self.page2, slug='child3', title='Child 3')

        def test_publish_with_overlapping_models(self):
            # make sure when we publish we don't accidentally create
            # multiple published versions
            self.failUnlessEqual(5, Page.objects.draft().count())
            self.failUnlessEqual(0, Page.objects.published().count())

            Page.objects.draft().publish()

            self.failUnlessEqual(5, Page.objects.draft().count())
            self.failUnlessEqual(5, Page.objects.published().count())

        def test_publish_with_overlapping_models_published(self):
            # make sure when we publish we don't accidentally create
            # multiple published versions
            self.failUnlessEqual(5, Page.objects.draft().count())
            self.failUnlessEqual(0, Page.objects.published().count())

            all_published = NestedSet()
            Page.objects.draft().publish(all_published)

            self.failUnlessEqual(5, len(all_published))

            self.failUnlessEqual(5, Page.objects.draft().count())
            self.failUnlessEqual(5, Page.objects.published().count())

        def test_publish_after_dry_run_handles_caching(self):
            # if we do a dry tun publish in the same queryset
            # before publishing for real, we have to make
            # sure we don't run into issues with the instance
            # caching parent's as None
            self.failUnlessEqual(5, Page.objects.draft().count())
            self.failUnlessEqual(0, Page.objects.published().count())

            draft = Page.objects.draft()

            all_published = NestedSet()
            for p in draft:
                p.publish(dry_run=True, all_published=all_published)

            # nothing published yet
            self.failUnlessEqual(5, Page.objects.draft().count())
            self.failUnlessEqual(0, Page.objects.published().count())

            # now publish (using same queryset, as this will have cached the instances)
            draft.publish()

            self.failUnlessEqual(5, Page.objects.draft().count())
            self.failUnlessEqual(5, Page.objects.published().count())

            # now actually check the public parent's are setup right
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            child1 = Page.objects.get(id=self.child1.id)
            child2 = Page.objects.get(id=self.child2.id)
            child3 = Page.objects.get(id=self.child3.id)

            self.failUnlessEqual(None, page1.public.parent)
            self.failUnlessEqual(None, page2.public.parent)
            self.failUnlessEqual(page1.public, child1.public.parent)
            self.failUnlessEqual(page1.public, child2.public.parent)
            self.failUnlessEqual(page2.public, child3.public.parent)
