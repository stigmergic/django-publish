from django.conf import settings

if getattr(settings, 'TESTING_PUBLISH', False):
    from django.test import TransactionTestCase

    from publish.models import Publishable
    from .models import Page, PageBlock, Author, Comment, Tag, PageTagOrder, Site, FlatPage

    class TestPublishableRecursiveForeignKey(TransactionTestCase):

        def setUp(self):
            super(TestPublishableRecursiveForeignKey, self).setUp()
            self.page1 = Page.objects.create(slug='page1', title='page 1', content='some content')
            self.page2 = Page.objects.create(slug='page2', title='page 2', content='other content', parent=self.page1)

        def test_publish_parent(self):
            # this shouldn't publish the child page
            self.page1.publish()
            self.failUnless(self.page1.public)
            self.failIf(self.page1.public.parent)

            page2 = Page.objects.get(id=self.page2.id)
            self.failIf(page2.public)

        def test_publish_child_parent_already_published(self):
            self.page1.publish()
            self.page2.publish()

            self.failUnless(self.page1.public)
            self.failUnless(self.page2.public)

            self.failIf(self.page1.public.parent)
            self.failUnless(self.page2.public.parent)

            self.failIfEqual(self.page1, self.page2.public.parent)

            self.failUnlessEqual('/page1/', self.page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', self.page2.public.get_absolute_url())

        def test_publish_child_parent_not_already_published(self):
            self.page2.publish()

            page1 = Page.objects.get(id=self.page1.id)
            self.failUnless(page1.public)
            self.failUnless(self.page2.public)

            self.failIf(page1.public.parent)
            self.failUnless(self.page2.public.parent)

            self.failIfEqual(page1, self.page2.public.parent)

            self.failUnlessEqual('/page1/', self.page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', self.page2.public.get_absolute_url())

        def test_publish_repeated(self):
            self.page1.publish()
            self.page2.publish()

            self.page1.slug = 'main'
            self.page1.save()

            self.failUnlessEqual('/main/', self.page1.get_absolute_url())

            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            self.failUnlessEqual('/page1/', page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', page2.public.get_absolute_url())

            page1.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            self.failUnlessEqual('/main/', page1.public.get_absolute_url())
            self.failUnlessEqual('/main/page2/', page2.public.get_absolute_url())

            page1.slug = 'elsewhere'
            page1.save()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            page2.slug = 'meanwhile'
            page2.save()
            page2.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)

            # only page2 should be published, not page1, as page1 already published
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page2.publish_state)
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, page1.publish_state)

            self.failUnlessEqual('/main/', page1.public.get_absolute_url())
            self.failUnlessEqual('/main/meanwhile/', page2.public.get_absolute_url())

            page1.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)

            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page2.publish_state)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page1.publish_state)

            self.failUnlessEqual('/elsewhere/', page1.public.get_absolute_url())
            self.failUnlessEqual('/elsewhere/meanwhile/', page2.public.get_absolute_url())

        def test_publish_deletions(self):
            self.page1.publish()
            self.page2.publish()

            self.page2.delete()
            self.failUnlessEqual([self.page2], list(Page.objects.deleted()))

            self.page2.publish()
            self.failUnlessEqual([self.page1.public], list(Page.objects.published()))
            self.failUnlessEqual([], list(Page.objects.deleted()))

        def test_publish_reverse_fields(self):
            page_block = PageBlock.objects.create(page=self.page1, content='here we are')

            self.page1.publish()

            public = self.page1.public
            self.failUnless(public)

            blocks = list(public.pageblock_set.all())
            self.failUnlessEqual(1, len(blocks))
            self.failUnlessEqual(page_block.content, blocks[0].content)

        def test_publish_deletions_reverse_fields(self):
            PageBlock.objects.create(page=self.page1, content='here we are')

            self.page1.publish()
            public = self.page1.public
            self.failUnless(public)

            self.page1.delete()

            self.failUnlessEqual([self.page1], list(Page.objects.deleted()))

            self.page1.publish()
            self.failUnlessEqual([], list(Page.objects.deleted()))
            self.failUnlessEqual([], list(Page.objects.all()))

        def test_publish_reverse_fields_deleted(self):
            # make sure child elements get removed
            page_block = PageBlock.objects.create(page=self.page1, content='here we are')

            self.page1.publish()

            public = self.page1.public
            page_block = PageBlock.objects.get(id=page_block.id)
            page_block_public = page_block.public
            self.failIf(page_block_public is None)

            self.failUnlessEqual([page_block_public], list(public.pageblock_set.all()))

            # now delete the page block and publish the parent
            # to make sure that deletion gets copied over properly
            page_block.delete()
            page1 = Page.objects.get(id=self.page1.id)
            page1.publish()
            public = page1.public

            self.failUnlessEqual([], list(public.pageblock_set.all()))

        def test_publish_delections_with_non_publishable_children(self):
            self.page1.publish()

            Comment.objects.create(page=self.page1.public, comment='This is a comment')

            self.failUnlessEqual(1, Comment.objects.count())

            self.page1.delete()

            self.failUnlessEqual([self.page1], list(Page.objects.deleted()))
            self.failIf(self.page1 in Page.objects.draft())

            self.page1.publish()
            self.failUnlessEqual([], list(Page.objects.deleted()))
            self.failUnlessEqual([], list(Page.objects.all()))
            self.failUnlessEqual([], list(Comment.objects.all()))

    class TestPublishableRecursiveManyToManyField(TransactionTestCase):

        def setUp(self):
            super(TestPublishableRecursiveManyToManyField, self).setUp()
            self.page = Page.objects.create(slug='page1', title='page 1', content='some content')
            self.author1 = Author.objects.create(name='author1', profile='a profile')
            self.author2 = Author.objects.create(name='author2', profile='something else')

        def test_publish_add_author(self):
            self.page.authors.add(self.author1)
            self.page.publish()
            self.failUnless(self.page.public)

            author1 = Author.objects.get(id=self.author1.id)
            self.failUnless(author1.public)
            self.failIfEqual(author1.id, author1.public.id)
            self.failUnlessEqual(author1.name, author1.public.name)
            self.failUnlessEqual(author1.profile, author1.public.profile)

            self.failUnlessEqual([author1.public], list(self.page.public.authors.all()))

        def test_publish_repeated_add_author(self):
            self.page.authors.add(self.author1)
            self.page.publish()

            self.failUnless(self.page.public)

            self.page.authors.add(self.author2)
            author1 = Author.objects.get(id=self.author1.id)
            self.failUnlessEqual([author1.public], list(self.page.public.authors.all()))

            self.page.publish()
            author1 = Author.objects.get(id=self.author1.id)
            author2 = Author.objects.get(id=self.author2.id)
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

        def test_publish_clear_authors(self):
            self.page.authors.add(self.author1, self.author2)
            self.page.publish()

            author1 = Author.objects.get(id=self.author1.id)
            author2 = Author.objects.get(id=self.author2.id)
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

            self.page.authors.clear()
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

            self.page.publish()
            self.failUnlessEqual([], list(self.page.public.authors.all()))

    class TestInfiniteRecursion(TransactionTestCase):

        def setUp(self):
            super(TestInfiniteRecursion, self).setUp()

            self.page1 = Page.objects.create(slug='page1', title='page 1')
            self.page2 = Page.objects.create(slug='page2', title='page 2', parent=self.page1)
            self.page1.parent = self.page2
            self.page1.save()

        def test_publish_recursion_breaks(self):
            self.page1.publish()  # this should simple run without an error

    class TestManyToManyThrough(TransactionTestCase):

        def setUp(self):
            super(TestManyToManyThrough, self).setUp()
            self.page = Page.objects.create(slug='p1', title='P 1')
            self.tag1 = Tag.objects.create(slug='tag1', title='Tag 1')
            self.tag2 = Tag.objects.create(slug='tag2', title='Tag 2')
            PageTagOrder.objects.create(tagged_page=self.page, page_tag=self.tag1, tag_order=2)
            PageTagOrder.objects.create(tagged_page=self.page, page_tag=self.tag2, tag_order=1)

        def test_publish_copies_tags(self):
            self.page.publish()

            self.failUnlessEqual(set([self.tag1, self.tag2]), set(self.page.public.tags.all()))

    class TestPublishableManyToMany(TransactionTestCase):

        def setUp(self):
            super(TestPublishableManyToMany, self).setUp()
            self.flat_page = FlatPage.objects.create(
                url='/my-page', title='my page',
                content='here is some content',
                enable_comments=False,
                registration_required=True)
            self.site1 = Site.objects.create(title='my site', domain='mysite.com')
            self.site2 = Site.objects.create(title='a site', domain='asite.com')

        def test_publish_no_sites(self):
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))

        def test_publish_add_site(self):
            self.flat_page.sites.add(self.site1)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))

        def test_publish_repeated_add_site(self):
            self.flat_page.sites.add(self.site1)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))

            self.flat_page.sites.add(self.site2)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))

            self.flat_page.publish()
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

        def test_publish_remove_site(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.sites.remove(self.site1)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.publish()
            self.failUnlessEqual([self.site2], list(self.flat_page.public.sites.all()))

        def test_publish_clear_sites(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.sites.clear()
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.publish()
            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))

        def test_publish_sites_cleared_not_deleted(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.flat_page.sites.clear()
            self.flat_page.publish()

            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))

            self.failIfEqual([], list(Site.objects.all()))
