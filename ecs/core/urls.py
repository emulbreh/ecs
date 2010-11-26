from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns(
    '',
    url(r'^$', 'django.views.generic.simple.redirect_to', {'url': '/dashboard/', 'permanent': True}),
    url(r'^autocomplete/(?P<queryset_name>[^/]+)/$', 'ecs.core.views.autocomplete'),

    url(r'^submission/(?P<submission_pk>\d+)/start_workflow/$', 'ecs.core.views.start_workflow'),
    url(r'^submission/(?P<submission_pk>\d+)/copy_form/$', 'ecs.core.views.copy_latest_submission_form'),
    url(r'^submission/(?P<submission_pk>\d+)/messages/send/$', 'ecs.communication.views.send_message'),
    url(r'^submission/(?P<submission_pk>\d+)/export/$', 'ecs.core.views.export_submission'),
    url(r'^submission/(?P<submission_pk>\d+)/tasks/log/$', 'ecs.tasks.views.task_backlog'),

    url(r'^submission_form/(?P<submission_form_pk>\d+)/$', 'ecs.core.views.readonly_submission_form'),
    url(r'^submission_form/(?P<submission_form_pk>\d+)/pdf/$', 'ecs.core.views.submission_pdf'),
    url(r'^submission_form/(?P<submission_form_pk>\d+)/copy/$', 'ecs.core.views.copy_submission_form'),
    url(r'^submission_form/(?P<submission_form_pk>\d+)/review/checklist/(?P<blueprint_pk>\d+)/$', 'ecs.core.views.checklist_review'),
    url(r'^submission_form/(?P<submission_form_pk>\d+)/review/categorization/$', 'ecs.core.views.categorization_review'),
    url(r'^submission_form/(?P<submission_form_pk>\d+)/review/thesis/$', 'ecs.core.views.retrospective_thesis_review'),
    url(r'^submission_form/(?P<submission_form_pk>\d+)/review/befangene/$', 'ecs.core.views.befangene_review'),
    url(r'^submission_form/(?P<submission_form_pk>\d+)/review/vote/$', 'ecs.core.views.vote_review'),
    url(r'^submission_form/(?P<submission_form_pk>\d+)/review/b2vote/$', 'ecs.core.views.b2_vote_review'),

    url(r'^submission_form/new/(?:(?P<docstash_key>.+)/)?$', 'ecs.core.views.create_submission_form'),
    url(r'^submission_form/delete/(?P<docstash_key>.+)/$', 'ecs.core.views.delete_docstash_entry'),
    url(r'^submission_form/import/$', 'ecs.core.views.import_submission_form'),
    url(r'^submission_forms/$', 'ecs.core.views.submission_forms'),
    url(r'^my_submission_forms/$', 'ecs.core.views.my_submission_forms'),
    url(r'^assigned_submission_forms/$', 'ecs.core.views.assigned_submission_forms'),
    url(r'^diff_submission_forms/(?P<old_submission_form_pk>\d+)/(?P<new_submission_form_pk>\d+)/$', 'ecs.core.views.diff'),
    url(r'^submission_widget/$', 'ecs.core.views.submission_widget'),
    url(r'^submission_list/$', 'ecs.core.views.submission_list'),
    
    url(r'^meeting/(?P<meeting_pk>\d+)/votes_signing/$', 'ecs.core.views.votes_signing'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_pdf/(?P<vote_pk>\d+)/$', 'ecs.core.views.vote_pdf'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_sign/(?P<vote_pk>\d+)/$', 'ecs.core.views.vote_sign'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_sign/(?P<vote_pk>\d+)/send$', 'ecs.core.views.vote_sign_send'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_sign/(?P<vote_pk>\d+)/error$', 'ecs.core.views.vote_sign_error'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_sign/(?P<vote_pk>\d+)/receive$', 'ecs.core.views.vote_sign_receive'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_sign/(?P<vote_pk>\d+)/preview$', 'ecs.core.views.vote_sign_preview'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_sign/(?P<vote_pk>\d+)/download$', 'ecs.core.views.download_signed_vote'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_sign/(?P<vote_pk>\d+)/show$', 'ecs.core.views.vote_show'),
    url(r'^meeting/(?P<meeting_pk>\d+)/vote_sign/(?P<vote_pk>\d+)/receive;jsessionid=null$', 'ecs.core.views.vote_sign_receive_landing'),
    
    url(r'^checklist/(?P<checklist_pk>\d+)/comments/(?P<flavour>positive|negative)/', 'ecs.core.views.checklist_comments'),

    url(r'^wizard/(?:(?P<docstash_key>.+)/)?$', 'ecs.core.views.wizard'),

    # public
    url(r'^catalog/$', 'ecs.core.views.submissions.catalog'),
)

