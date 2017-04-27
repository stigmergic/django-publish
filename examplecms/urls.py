from django.conf.urls import include, url
from django.conf import settings
from django.contrib import admin
from django.views import static

urlpatterns = [
    url('^admin/', include(admin.site.urls)),

    url(r'^media/(?P<path>.*)$', static.serve, {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    
    url('^', include('pubcms.urls')),
]
