from django.db import models
from datetime import datetime
from publish.models import Publishable


class Site(models.Model):
    title = models.CharField(max_length=100)
    domain = models.CharField(max_length=100)


class FlatPage(Publishable):
    url = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    enable_comments = models.BooleanField()
    template_name = models.CharField(max_length=70, blank=True)
    registration_required = models.BooleanField()
    sites = models.ManyToManyField(Site)

    class Meta:
        ordering = ['url']

    def get_absolute_url(self):
        if self.is_public:
            return self.url
        return '%s*' % self.url


class Author(Publishable):
    name = models.CharField(max_length=100)
    profile = models.TextField(blank=True)

    class PublishMeta(Publishable.PublishMeta):
        publish_reverse_fields = ['authorprofile']


class AuthorProfile(Publishable):
    author = models.OneToOneField(Author)
    extra_profile = models.TextField(blank=True)


class ChangeLog(models.Model):
    changed = models.DateTimeField(db_index=True, auto_now_add=True)
    message = models.CharField(max_length=200)


class Tag(models.Model):
    title = models.CharField(max_length=100, unique=True)
    slug = models.CharField(max_length=100)


# publishable model with a reverse relation to
# page (as a child)
class PageBlock(Publishable):
    page = models.ForeignKey('Page')
    content = models.TextField(blank=True)


# non-publishable reverse relation to page (as a child)
class Comment(models.Model):
    page = models.ForeignKey('Page')
    comment = models.TextField()


def update_pub_date(page, field_name, value):
    # ignore value entirely and replace with now
    setattr(page, field_name, update_pub_date.pub_date)
update_pub_date.pub_date = datetime.now()


class Page(Publishable):
    slug = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    pub_date = models.DateTimeField(default=datetime.now)

    parent = models.ForeignKey('self', blank=True, null=True)

    authors = models.ManyToManyField(Author, blank=True)
    log = models.ManyToManyField(ChangeLog, blank=True)
    tags = models.ManyToManyField(Tag, through='PageTagOrder', blank=True)

    class Meta:
        ordering = ['slug']

    class PublishMeta(Publishable.PublishMeta):
        publish_exclude_fields = ['log']
        publish_reverse_fields = ['pageblock_set']
        publish_functions = {'pub_date': update_pub_date}

    def get_absolute_url(self):
        if not self.parent:
            return u'/%s/' % self.slug
        return '%s%s/' % (self.parent.get_absolute_url(), self.slug)


class PageTagOrder(Publishable):
    # note these are named in non-standard way to
    # ensure we are getting correct names
    tagged_page = models.ForeignKey(Page)
    page_tag = models.ForeignKey(Tag)
    tag_order = models.IntegerField()
