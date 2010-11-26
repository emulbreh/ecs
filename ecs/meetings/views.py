import datetime

from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils import simplejson
from django.contrib.auth.models import User
from django.utils.datastructures import SortedDict
from django.db.models import Count
from django.utils.translation import ugettext as _

from ecs.utils.viewutils import render, render_html, render_pdf, pdf_response
from ecs.utils.decorators import developer
from ecs.users.utils import user_flag_required
from ecs.core.models import Submission, MedicalCategory, Vote, ChecklistBlueprint
from ecs.core.forms.voting import VoteForm, SaveVoteForm
from ecs.documents.models import Document

from ecs.meetings.tasks import optimize_timetable_task
from ecs.meetings.models import Meeting, Participation, TimetableEntry, AssignedMedicalCategory, Participation
from ecs.meetings.forms import (MeetingForm, TimetableEntryForm, FreeTimetableEntryForm, UserConstraintFormSet, 
    SubmissionSchedulingForm, SubmissionReschedulingForm, AssignedMedicalCategoryForm, MeetingAssistantForm)

from ecs.ecsmail.mail import deliver
from ecs.ecsmail.persil import whitewash


def create_meeting(request):
    form = MeetingForm(request.POST or None)
    if form.is_valid():
        meeting = form.save()
        return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'meetings/form.html', {
        'form': form,
    })
    
def meeting_list(request, meetings):
    return render(request, 'meetings/list.html', {
        'meetings': meetings.order_by('start')
    })
    
def upcoming_meetings(request):
    return meeting_list(request, Meeting.objects.filter(start__gte=datetime.datetime.now()))

def past_meetings(request):
    return meeting_list(request, Meeting.objects.filter(start__lt=datetime.datetime.now()))

@developer
def schedule_submission(request, submission_pk=None):
    """ Developer: this will happen automatically """
    submission = get_object_or_404(Submission, pk=submission_pk)
    form = SubmissionSchedulingForm(request.POST or None)
    if form.is_valid():
        kwargs = form.cleaned_data.copy()
        meeting = kwargs.pop('meeting')
        timetable_entry = meeting.add_entry(submission=submission, duration=datetime.timedelta(minutes=7.5), **kwargs)
        return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'submissions/schedule.html', {
        'submission': submission,
        'form': form,
    })

@user_flag_required('executive_board_member')
def reschedule_submission(request, submission_pk=None):
    submission = get_object_or_404(Submission, pk=submission_pk)
    form = SubmissionReschedulingForm(request.POST or None, submission=submission)
    if form.is_valid():
        from_meeting = form.cleaned_data['from_meeting']
        to_meeting = form.cleaned_data['to_meeting']
        old_entries = from_meeting.timetable_entries.filter(submission=submission)
        for entry in old_entries:
            to_meeting.add_entry(submission=submission, duration=entry.duration, title=entry.title)
        old_entries.delete()
        return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': to_meeting.pk}))
    return render(request, 'meetings/reschedule.html', {
        'submission': submission,
        'form': form,
    })
    
def add_free_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    form = FreeTimetableEntryForm(request.POST or None)
    if form.is_valid():
        entry = meeting.add_entry(**form.cleaned_data)
        return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'meetings/timetable/add_free_entry.html', {
        'form': form,
        'meeting': meeting,
    })
    

def add_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    is_break = request.GET.get('break', False)
    if is_break:
        entry = meeting.add_break(duration=datetime.timedelta(minutes=30))
    else:
        entry = meeting.add_entry(duration=datetime.timedelta(minutes=7, seconds=30), submission=Submission.objects.order_by('?')[:1].get())
        import random
        for user in User.objects.order_by('?')[:random.randint(1, 4)]:
            Participation.objects.create(entry=entry, user=user)
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
def remove_timetable_entry(request, meeting_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    entry = get_object_or_404(TimetableEntry, pk=entry_pk)
    entry.delete()
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
def update_timetable_entry(request, meeting_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    entry = get_object_or_404(TimetableEntry, pk=entry_pk)
    form = TimetableEntryForm(request.POST)
    if form.is_valid():
        entry.duration = form.cleaned_data['duration']
        entry.optimal_start = form.cleaned_data['optimal_start']
        entry.save()
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
def move_timetable_entry(request, meeting_pk=None):
    from_index = int(request.GET.get('from_index'))
    to_index = int(request.GET.get('to_index'))
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    meeting[from_index].index = to_index
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
def users_by_medical_category(request):
    category = get_object_or_404(MedicalCategory, pk=request.POST.get('category'))
    users = list(User.objects.filter(medical_categories=category, ecs_profile__board_member=True).values('pk', 'username'))
    return HttpResponse(simplejson.dumps(users), content_type='text/json')

def timetable_editor(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    return render(request, 'meetings/timetable/editor.html', {
        'meeting': meeting,
        'running_optimization': bool(meeting.optimization_task_id),
    })
    
def medical_categories(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    required_categories = MedicalCategory.objects.filter(submissions__timetable_entries__meeting=meeting).order_by('abbrev')

    forms = SortedDict()
    for cat in required_categories:
        forms[cat] = AssignedMedicalCategoryForm(request.POST or None, meeting=meeting, category=cat, prefix='cat%s' % cat.pk)

    if request.method == 'POST':
        for cat, form in forms.iteritems():
            if form.is_valid():
                if form.instance and form.instance.board_member:
                    # remove all participations for a previous selected board member.
                    # XXX: this may delete manually entered data. (FMD2)
                    Participation.objects.filter(medical_category=cat, entry__meeting=meeting).delete()
                amc = form.save()
                # add participations for all timetable entries with matching categories.
                # this assumes that all submissions have already been added to the meeting.
                for entry in meeting.timetable_entries.filter(submission__medical_categories=cat).distinct():
                    Participation.objects.get_or_create(medical_category=cat, entry=entry, user=amc.board_member)

    return render(request, 'meetings/timetable/medical_categories.html', {
        'meeting': meeting,    
        'forms': forms,
    })

def optimize_timetable(request, meeting_pk=None, algorithm=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    if not meeting.optimization_task_id:
        meeting.optimization_task_id = "xxx:fake"
        meeting.save()
        retval = optimize_timetable_task.apply_async(kwargs={'meeting_id': meeting.id, 'algorithm': algorithm})
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))

def edit_user_constraints(request, meeting_pk=None, user_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    user = get_object_or_404(User, pk=user_pk)
    constraint_formset = UserConstraintFormSet(request.POST or None, prefix='constraint', queryset=user.meeting_constraints.all())
    if constraint_formset.is_valid():
        for constraint in constraint_formset.save(commit=False):
            constraint.meeting = meeting
            constraint.user = user
            constraint.save()
        return HttpResponseRedirect(reverse('ecs.meetings.views.meetings.edit_user_constraints', kwargs={'meeting_pk': meeting.pk, 'user_pk': user.pk}))
    return render(request, 'meetings/constraints/user_form.html', {
        'meeting': meeting,
        'participant': user,
        'constraint_formset': constraint_formset,
    })
    
def meeting_assistant_quickjump(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    top = None
    q = request.REQUEST.get('q', '').upper()
    explict_top = 'TOP' in q
    q = q.replace('TOP', '').strip()
    
    # if we don't explicitly look for a TOP, try an exact ec_number lookup
    if not explict_top:
        tops = meeting.timetable_entries.filter(submission__ec_number__endswith=q).order_by('timetable_index')
        if len(tops) == 1:
            top = tops[0]
    # if we found no TOP yet, try an exact TOP index lookup
    if not top:
        try:
            top = meeting.timetable_entries.get(timetable_index=int(q)-1)
        except (ValueError, TimetableEntry.DoesNotExist):
            pass
    # if we found no TOP yet and don't explicitly look for a TOP, try a fuzzy ec_number lookup
    if not top and not explict_top:
        tops = meeting.timetable_entries.filter(submission__ec_number__icontains=q).order_by('timetable_index')
        if len(tops) == 1:
            top = tops[0]
    if top:
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': top.pk}))
    
    return render(request, 'meetings/assistant/quickjump_error.html', {
        'meeting': meeting,
        'tops': tops,
    })
    
def meeting_assistant(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    if meeting.started:
        if meeting.ended:
            return render(request, 'meetings/assistant/error.html', {
                'meeting': meeting,
                'message': _(u'This meeting has ended.'),
            })
        try:
            top_pk = request.session.get('meetings:%s:assistant:top_pk' % meeting.pk, None) or meeting[0].pk
            return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': top_pk}))
        except IndexError:
            return render(request, 'meetings/assistant/error.html', {
                'meeting': meeting,
                'message': _(u'No TOPs are assigned to this meeting.'),
            })
    else:
        return render(request, 'meetings/assistant/error.html', {
            'meeting': meeting,
            'message': _('This meeting has not yet started.'),
        })
        
def meeting_assistant_start(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    meeting.started = datetime.datetime.now()
    meeting.save()
    return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))
    
def meeting_assistant_stop(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    if meeting.open_tops.count():
        raise Http404(_("unfinished meetings cannot be stopped"))
    meeting.ended = datetime.datetime.now()
    meeting.save()
    return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))
    
def meeting_assistant_comments(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    form = MeetingAssistantForm(request.POST or None, instance=meeting)
    if form.is_valid():
        form.save()
        if request.POST.get('autosave', False):
            return HttpResponse('OK')
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'meetings/assistant/comments.html', {
        'meeting': meeting,
        'form': form,
    })

def meeting_assistant_top(request, meeting_pk=None, top_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    top = get_object_or_404(TimetableEntry, pk=top_pk)
    simple_save = request.POST.get('simple_save', False)
    autosave = request.POST.get('autosave', False)
    vote, form = None, None
    
    def next_top_redirect():
        if top.next_open:
            next_top = top.next_open
        else:
            try:
                next_top = meeting.open_tops[0]
            except IndexError:
                return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': next_top.pk}))
    
    if top.submission:
        try:
            vote = top.vote
        except Vote.DoesNotExist:
            pass
        if simple_save:
            form_cls = SaveVoteForm
        else:
            form_cls = VoteForm
        form = form_cls(request.POST or None, instance=vote)
        if form.is_valid():
            vote = form.save(commit=False)
            vote.top = top
            vote.save()
            if autosave:
                return HttpResponse('OK')
            if form.cleaned_data['close_top']:
                top.is_open = False
                top.save()
            return next_top_redirect()
    elif request.method == 'POST':
        top.is_open = False
        top.save()
        return next_top_redirect()

    last_top_cache_key = 'meetings:%s:assistant:top_pk' % meeting.pk
    last_top = None
    if last_top_cache_key in request.session:
        last_top = TimetableEntry.objects.get(pk=request.session[last_top_cache_key])
    request.session[last_top_cache_key] = top.pk
    
    checklist_review_states = SortedDict()
    if top.submission:
        for blueprint in ChecklistBlueprint.objects.order_by('name'):
            checklist_review_states[blueprint] = []
        for checklist in top.submission.checklists.select_related('blueprint'):
            checklist_review_states[checklist.blueprint].append(checklist)

    return render(request, 'meetings/assistant/top.html', {
        'meeting': meeting,
        'submission': top.submission,
        'top': top,
        'vote': vote,
        'form': form,
        'last_top': last_top,
        'checklist_review_states': checklist_review_states.items(),
    })

def meeting_assistant_clear(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    Vote.objects.filter(top__meeting=meeting).delete()
    meeting.timetable_entries.update(is_open=True)
    meeting.started = None
    meeting.ended = None
    meeting.save()
    return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))


def agenda_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    filename = '%s-%s-%s.pdf' % (
        meeting.title, meeting.start.strftime('%d-%m-%Y'), _('agenda')
    )
    
    pdf = render_pdf(request, 'db/meetings/xhtml2pdf/agenda.html', {
        'meeting': meeting,
    })
    return pdf_response(pdf, filename=filename)

def protocol_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    filename = '%s-%s-%s.pdf' % (
        meeting.title, meeting.start.strftime('%d-%m-%Y'), _('protocol')
    )
    
    timetable_entries = meeting.timetable_entries.all().order_by('timetable_index')
    tops = []
    for top in timetable_entries:
        try:
            vote = Vote.objects.filter(top=top)[0]
        except IndexError:
            vote = None
        tops.append((top, vote,))

    b2_votes = Vote.objects.filter(result='2', top__in=timetable_entries)
    submission_forms = [x.submission_form for x in b2_votes]
    b1ized = Vote.objects.filter(result__in=['1', '1a'], submission_form__in=submission_forms).order_by('submission_form__submission__ec_number')

    pdf = render_pdf(request, 'db/meetings/xhtml2pdf/protocol.html', {
        'meeting': meeting,
        'tops': tops,
        'b1ized': b1ized,
    })
    return pdf_response(pdf, filename=filename)


def timetable_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    
    timetable = {}
    for entry in meeting:
        for user in entry.users:
            if user in timetable:
                timetable[user].append(entry)
            else:
                timetable[user] = [entry]
    
    timetable = sorted([{
        'user': key,
        'entries': sorted(timetable[key], key=lambda x:x.timetable_index),
    } for key in timetable], key=lambda x:x['user'])
    
    for row in timetable:
        first_entry = row['entries'][0]
        times = [{'start': first_entry.start, 'end': first_entry.end, 'index': first_entry.timetable_index}]
        for entry in row['entries'][1:]:
            if times[-1]['end'] == entry.start:
                times[-1]['end'] = entry.end
            else:
                times.append({'start': entry.start, 'end': entry.end, 'index': entry.timetable_index})
    
        row['times'] = ', '.join(['%s - %s' % (x['start'].strftime('%H:%M'), x['end'].strftime('%H:%M')) for x in times])
    
    filename = '%s-%s-%s.pdf' % (
        meeting.title, meeting.start.strftime('%d-%m-%Y'), _('time slot')
    )
    
    pdf = render_pdf(request, 'db/meetings/xhtml2pdf/timetable.html', {
        'meeting': meeting,
        'timetable': timetable,
    })
    return pdf_response(pdf, filename=filename)

def agenda_htmlemail(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    filename = '%s-%s-%s.pdf' % (
        meeting.title, meeting.start.strftime('%d-%m-%Y'), _('agenda')
    )
    pdf = render_pdf(request, 'db/meetings/xhtml2pdf/agenda.html', {
        'meeting': meeting,
    })

    for recipient in settings.AGENDA_RECIPIENT_LIST:        
        htmlmail = unicode(render_html(request, 'meetings/email/invitation-with-agenda.html', {
            'meeting': meeting,
            'recipient': recipient,
        }))
        plainmail = whitewash(htmlmail)

        deliver(subject=_('Invitation to meeting'), 
            message=plainmail,
            message_html=htmlmail,
            attachments=[(filename, pdf,'application/pdf'),],
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=settings.AGENDA_RECIPIENT_LIST)

    return HttpResponseRedirect(reverse('ecs.meetings.views.upcoming_meetings'))

def timetable_htmlemailpart(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    response = render(request, 'meetings/email/timetable.html', {
        'meeting': meeting,
    })
    return response

def next(request):
    try:
        meeting = Meeting.objects.all().order_by('-start')[0]
    except IndexError:
        return HttpResponseRedirect(reverse('ecs.dashboard.views.view_dashboard'))

    return HttpResponseRedirect(reverse('ecs.meetings.views.status', kwargs={'meeting_pk': meeting.pk}))

def status(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    return render(request, 'meetings/status.html', {
        'meeting': meeting,
    })

