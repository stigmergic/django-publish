from django.conf import settings

if getattr(settings, 'TESTING_PUBLISH', False):
    from django.conf.urls import patterns, include
    from django.contrib.admin.sites import AdminSite
    from django.contrib.auth.models import User
    from django.core.exceptions import PermissionDenied
    from django.forms.models import ModelChoiceField, ModelMultipleChoiceField
    from django.test import TransactionTestCase
    from unittest import skip

    from publish.actions import _convert_all_published_to_html, publish_selected, unpublish_selected
    from publish.admin import PublishableAdmin, PublishableStackedInline
    from publish.models import Publishable, Page, PageBlock, Author
    from publish.utils import NestedSet
    from . import RequestFactoryMixin

    class TestPublishableAdmin(TransactionTestCase, RequestFactoryMixin):

        def setUp(self):
            super(TestPublishableAdmin, self).setUp()
            self.page1 = Page.objects.create(slug='page1', title='page 1')
            self.page2 = Page.objects.create(slug='page2', title='page 2')
            self.page1.publish()
            self.page2.publish()

            self.author1 = Author.objects.create(name='a1')
            self.author2 = Author.objects.create(name='a2')
            self.author1.publish()
            self.author2.publish()

            self.admin_site = AdminSite('Test Admin')

            class PageBlockInline(PublishableStackedInline):
                model = PageBlock

            class PageAdmin(PublishableAdmin):
                inlines = [PageBlockInline]

            self.admin_site.register(Page, PageAdmin)
            self.page_admin = PageAdmin(Page, self.admin_site)

            # override urls, so reverse works
            settings.ROOT_URLCONF = patterns(
                '',
                ('^admin/', include(self.admin_site.urls)),
            )

        def test_get_publish_status_display(self):
            page = Page.objects.create(slug="hhkkk", title="hjkhjkh")
            self.failUnlessEqual('Changed - not yet published', self.page_admin.get_publish_status_display(page))
            page.publish()
            self.failUnlessEqual('Published', self.page_admin.get_publish_status_display(page))
            page.save()
            self.failUnlessEqual('Changed', self.page_admin.get_publish_status_display(page))

            page.delete()
            self.failUnlessEqual('To be deleted', self.page_admin.get_publish_status_display(page))

        def test_queryset(self):
            # make sure we only get back draft objects
            request = None

            self.failUnlessEqual(
                set([self.page1, self.page1.public, self.page2, self.page2.public]),
                set(Page.objects.all())
            )
            self.failUnlessEqual(
                set([self.page1, self.page2]),
                set(self.page_admin.queryset(request))
            )

        def test_get_actions_global_delete_replaced(self):
            from publish.actions import delete_selected

            class request(object):
                GET = {}

            actions = self.page_admin.get_actions(request)

            self.failUnless('delete_selected' in actions)
            action, name, description = actions['delete_selected']
            self.failUnlessEqual(delete_selected, action)
            self.failUnlessEqual('delete_selected', name)
            self.failUnlessEqual(delete_selected.short_description, description)

        def test_formfield_for_foreignkey(self):
            # foreign key forms fields in admin
            # for publishable models should be filtered
            # to hide public object

            request = None
            parent_field = None
            for field in Page._meta.fields:
                if field.name == 'parent':
                    parent_field = field
                    break
            self.failUnless(parent_field)

            choice_field = self.page_admin.formfield_for_foreignkey(parent_field, request)
            self.failUnless(choice_field)
            self.failUnless(isinstance(choice_field, ModelChoiceField))

            self.failUnlessEqual(
                set([self.page1, self.page1.public, self.page2, self.page2.public]),
                set(Page.objects.all())
            )
            self.failUnlessEqual(
                set([self.page1, self.page2]),
                set(choice_field.queryset)
            )

        def test_formfield_for_manytomany(self):
            request = None
            authors_field = None
            for field in Page._meta.many_to_many:
                if field.name == 'authors':
                    authors_field = field
                    break
            self.failUnless(authors_field)

            choice_field = self.page_admin.formfield_for_manytomany(authors_field, request)
            self.failUnless(choice_field)
            self.failUnless(isinstance(choice_field, ModelMultipleChoiceField))

            self.failUnlessEqual(
                set([self.author1, self.author1.public, self.author2, self.author2.public]),
                set(Author.objects.all())
            )
            self.failUnlessEqual(
                set([self.author1, self.author2]),
                set(choice_field.queryset)
            )

        def test_has_change_permission(self):
            class dummy_request(object):
                method = 'GET'
                REQUEST = {}

                class user(object):
                    @classmethod
                    def has_perm(cls, permission):
                        return True

            self.failUnless(self.page_admin.has_change_permission(dummy_request))
            self.failUnless(self.page_admin.has_change_permission(dummy_request, self.page1))
            self.failIf(self.page_admin.has_change_permission(dummy_request, self.page1.public))

            # can view deleted items
            self.page1.publish_state = Publishable.PUBLISH_DELETE
            self.failUnless(self.page_admin.has_change_permission(dummy_request, self.page1))

            # but cannot modify them
            dummy_request.method = 'POST'
            self.failIf(self.page_admin.has_change_permission(dummy_request, self.page1))

        def test_has_delete_permission(self):
            class dummy_request(object):
                method = 'GET'
                REQUEST = {}

                class user(object):
                    @classmethod
                    def has_perm(cls, permission):
                        return True

            self.failUnless(self.page_admin.has_delete_permission(dummy_request))
            self.failUnless(self.page_admin.has_delete_permission(dummy_request, self.page1))
            self.failIf(self.page_admin.has_delete_permission(dummy_request, self.page1.public))

        def test_change_view_normal(self):
            dummy_request = self.build_get_request()

            response = self.page_admin.change_view(dummy_request, str(self.page1.id))
            self.failUnless(response is not None)
            # self.failIf('deleted' in _get_rendered_content(response))

        @skip('weird error')
        def test_change_view_not_deleted(self):
            dummy_request = self.build_get_request(**{'wsgi.url_scheme': 'http'})

            response = self.page_admin.change_view(dummy_request, unicode(self.page1.public.id))
            # should be redirecting to the draft version
            self.failUnless(response is not None)
            self.assertEquals(302, response.status_code)
            self.assertEquals('/admin/publish/page/%d/' % self.page1.id, response['Location'])

        def test_change_view_deleted(self):
            dummy_request = self.build_get_request()
            self.page1.delete()

            response = self.page_admin.change_view(dummy_request, str(self.page1.id))
            self.failUnless(response is not None)
            # self.failUnless('deleted' in _get_rendered_content(response))

        def test_change_view_deleted_POST(self):
            dummy_request = self.build_post_request({})

            self.page1.delete()

            try:
                self.page_admin.change_view(dummy_request, str(self.page1.id))
                self.fail()
            except PermissionDenied:
                pass

        @skip('Failing due to NoReverseMatch error')
        def test_change_view_delete_inline(self):
            block = PageBlock.objects.create(page=self.page1, content='some content')
            page1 = Page.objects.get(pk=self.page1.pk)
            page1.publish()

            # fake selecting the delete tickbox for the block
            dummy_request = self.build_post_request({
                'slug': page1.slug,
                'title': page1.title,
                'content': page1.content,
                'pub_date_0': '2010-02-12',
                'pub_date_1': '17:40:00',
                'pageblock_set-TOTAL_FORMS': '2',
                'pageblock_set-INITIAL_FORMS': '1',
                'pageblock_set-0-id': str(block.id),
                'pageblock_set-0-page': str(page1.id),
                'pageblock_set-0-DELETE': 'yes'
            })

            block = PageBlock.objects.get(id=block.id)
            public_block = block.public

            response = self.page_admin.change_view(dummy_request, str(page1.id))
            self.assertEqual(302, response.status_code)

            # the block should have been deleted (but not the public one)
            self.failUnlessEqual([public_block], list(PageBlock.objects.all()))

    class TestPublishSelectedAction(TransactionTestCase, RequestFactoryMixin):

        def setUp(self):
            super(TestPublishSelectedAction, self).setUp()
            self.fp1 = Page.objects.create(slug='fp1', title='FP1')
            self.fp2 = Page.objects.create(slug='fp2', title='FP2')
            self.fp3 = Page.objects.create(slug='fp3', title='FP3')

            self.admin_site = AdminSite('Test Admin')
            self.page_admin = PublishableAdmin(Page, self.admin_site)
            self.user = User.objects.create_user('test1', 'test@example.com', 'jkljkl')
            # override urls, so reverse works
            settings.ROOT_URLCONF = patterns(
                '',
                ('^admin/', include(self.admin_site.urls)),
            )

        def test_publish_selected_confirm(self):
            pages = Page.objects.exclude(id=self.fp3.id)

            class dummy_request(object):
                META = {}
                POST = {}

                class user(object):
                    @classmethod
                    def has_perm(cls, *arg):
                        return True

                    @classmethod
                    def get_and_delete_messages(cls):
                        return []

            response = publish_selected(self.page_admin, dummy_request, pages)

            self.failIf(Page.objects.published().count() > 0)
            self.failUnless(response is not None)
            self.failUnlessEqual(200, response.status_code)

        def test_publish_selected_confirmed(self):
            pages = Page.objects.exclude(id=self.fp3.id)
            dummy_request = self.build_post_request({'post': True})

            response = publish_selected(self.page_admin, dummy_request, pages)
            self.failUnlessEqual(2, Page.objects.published().count())
            # self.failUnless(getattr(self, '_message', None) is not None)
            self.failUnless(response is None)

        def test_convert_all_published_to_html(self):
            self.admin_site.register(Page, PublishableAdmin)

            all_published = NestedSet()

            page = Page.objects.create(slug='here', title='title')
            block = PageBlock.objects.create(page=page, content='stuff here')

            all_published.add(page)
            all_published.add(block, parent=page)

            converted = _convert_all_published_to_html(self.admin_site, all_published)

            expected = [u'<a href="../../publish/page/%d/">Page: Page object (Changed - not yet published)</a>' % page.id, [u'Page block: PageBlock object']]

            self.failUnlessEqual(expected, converted)

        def test_publish_selected_does_not_have_permission(self):
            self.admin_site.register(Page, PublishableAdmin)
            pages = Page.objects.exclude(id=self.fp3.id)
            dummy_request = self.build_post_request({})
            dummy_request.user = self.build_common_user()

            response = publish_selected(self.page_admin, dummy_request, pages)
            self.failIf(response is None)
            # publish button should not be in response
            self.failIf('value="publish_selected"' in response.content)
            self.failIf('value="Yes, Publish"' in response.content)
            self.failIf('form' in response.content)

            self.failIf(Page.objects.published().count() > 0)

        def test_publish_selected_does_not_have_related_permission(self):
            # check we can't publish when we don't have permission
            # for a related model (in this case authors)
            self.admin_site.register(Author, PublishableAdmin)

            author = Author.objects.create(name='John')
            self.fp1.authors.add(author)
            pages = Page.objects.draft()
            dummy_request = self.build_post_request({'post': True})
            dummy_request.user = self.build_common_user()
            try:
                publish_selected(self.page_admin, dummy_request, pages)
                self.fail()
            except PermissionDenied:
                pass

            self.failIf(Page.objects.published().count() > 0)

        def test_publish_selected_logs_publication(self):
            self.admin_site.register(Page, PublishableAdmin)

            pages = Page.objects.exclude(id=self.fp3.id)

            dummy_request = self.build_post_request({'post': True})
            publish_selected(self.page_admin, dummy_request, pages)

            # should have logged two publications
            from django.contrib.admin.models import LogEntry
            from django.contrib.contenttypes.models import ContentType

            ContentType.objects.get_for_model(self.fp1).pk
            self.failUnlessEqual(2, LogEntry.objects.filter().count())

    class TestUnpublishSelectedAction(TransactionTestCase, RequestFactoryMixin):

        def setUp(self):
            super(TestUnpublishSelectedAction, self).setUp()

            self.fp1 = Page.objects.create(slug='fp1', title='FP1')
            self.fp2 = Page.objects.create(slug='fp2', title='FP2')
            self.fp3 = Page.objects.create(slug='fp3', title='FP3')

            self.fp1.save()
            self.fp2.save()
            self.fp3.save()

            for page in Page.objects.draft():
                page.publish()

            self.admin_site = AdminSite('Test Admin')
            self.page_admin = PublishableAdmin(Page, self.admin_site)

            self.user = User.objects.create_user('test1', 'test@example.com', 'jkljkl')

            # override urls, so reverse works
            settings.ROOT_URLCONF = patterns(
                '',
                ('^admin/', include(self.admin_site.urls)),
            )

        def test_unpublish_selected_confirm(self):
            pages = Page.objects.draft()

            dummy_request = self.build_post_request({})
            response = unpublish_selected(self.page_admin, dummy_request, pages)

            self.failIf(Page.objects.draft().count() != 3)
            self.failUnless(response is not None)
            self.failUnlessEqual(200, response.status_code)

        def test_publish_selected_confirmed(self):
            pages = Page.objects.draft()

            dummy_request = self.build_post_request({'post': True})
            response = unpublish_selected(self.page_admin, dummy_request, pages)

            self.failUnlessEqual(0, Page.objects.published().count())
            self.failUnlessEqual(3, Page.objects.draft().count())
            # self.failUnless(getattr(self, '_message', None) is not None)
            self.failUnless(response is None)
