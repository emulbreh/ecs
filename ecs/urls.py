from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
from django.views.static import serve
from django.views.generic.simple import direct_to_template
from ecs.utils import forceauth
from ecs import workflow
import django

# stuff that needs called at the beginning, but not in settings.py

admin.autodiscover()
workflow.autodiscover()

import logging
from sentry.client.handlers import SentryHandler
logging.getLogger().addHandler(SentryHandler())

# Add StreamHandler to sentry's default so you can catch missed exceptions
logger = logging.getLogger('sentry.errors')
logger.propagate = False
logger.addHandler(logging.StreamHandler())


urlpatterns = patterns('',
    url(r'^$', 'django.views.generic.simple.redirect_to', {'url': '/dashboard/'}),

    url(r'^audit/', include('ecs.audit.urls')),
    url(r'^core/', include('ecs.core.urls')),
    url(r'^dashboard/', include('ecs.dashboard.urls')),
    url(r'^fastlane/', include('ecs.fastlane.urls')),

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    url(r'^feedback/', include('ecs.feedback.urls')),
    url(r'^userswitcher/', include('ecs.userswitcher.urls')),
    url(r'^pdfviewer/', include('ecs.pdfviewer.urls')),
    url(r'^mediaserver/', include('ecs.mediaserver.urls')),
    url(r'^tasks/', include('ecs.tasks.urls')),
    url(r'^communication/', include('ecs.communication.urls')),
    url(r'^billing/', include('ecs.billing.urls')),
    url(r'^help/', include('ecs.help.urls')),
    url(r'^', include('ecs.users.urls')),
    url(r'^', include('ecs.documents.urls')),
    url(r'^', include('ecs.meetings.urls')),
    url(r'^', include('ecs.notifications.urls')),

    url(r'^static/(?P<path>.*)$', forceauth.exempt(serve), {'document_root': settings.MEDIA_ROOT}),
    url(r'^bugshot/', include('ecs.bugshot.urls')),
    url(r'^search/', include('haystack.urls')),
    url(r'^test/', direct_to_template, {'template': 'test.html'}),
    #url(r'^tests/killableprocess/$', 'ecs.utils.tests.killableprocess.timeout_view'),
    
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^sentry/', include('sentry.urls')),
)

