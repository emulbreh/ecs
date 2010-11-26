from datetime import datetime
from django.db.models.signals import post_save
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from ecs.workflow import Activity, guard, register
from ecs.workflow.patterns import Generic
from ecs.users.utils import get_current_user
from ecs.core.models import Submission, ChecklistBlueprint, Checklist, Vote

register(Submission, autostart_if=lambda s: bool(s.current_submission_form_id))
register(Vote)

@guard(model=Submission)
def is_acknowledged(wf):
    return wf.data.current_submission_form.acknowledged
    

@guard(model=Submission)
def is_thesis(wf):
    if wf.data.thesis is None:
        return wf.data.current_submission_form.project_type_education_context is not None
    return wf.data.thesis
    

@guard(model=Submission)
def has_b2vote(wf):
    sf = wf.data.current_submission_form
    if sf.current_pending_vote:
        return sf.current_pending_vote.result == '2'
    if sf.current_published_vote:
        return sf.current_published_vote.result == '2'
    return False

@guard(model=Vote)
def is_executive_vote_review_required(wf):
    return wf.data.executive_review_required


@guard(model=Vote)
def is_final(wf):
    return wf.data.final
    
@guard(model=Vote)
def is_b2upgrade(wf):
    previous_vote = wf.data.submission_form.votes.filter(pk__lt=wf.data.pk).order_by('-pk')[:1]
    return wf.data.activates and previous_vote and previous_vote[0].result == '2'

@guard(model=Submission)
def is_expedited(wf):
    return bool(wf.data.expedited)
    

@guard(model=Submission)
def has_recommendation(wf):
    return False # FIXME: missing feature (FMD3)


@guard(model=Submission)
def has_accepted_recommendation(wf):
    return False # FIXME: missing feature (FMD3)

@guard(model=Submission)
def needs_external_review(wf):
    return wf.data.external_reviewer
    
class InitialReview(Activity):
    class Meta:
        model = Submission
    
    def get_url(self):
        return reverse('ecs.core.views.readonly_submission_form', kwargs={'submission_form_pk': self.workflow.data.current_submission_form_id})
        
    def get_choices(self):
        return (
            (True, _('Acknowledge')),
            (False, _('Reject')),
        )
        
    def pre_perform(self, choice):
        sf = self.workflow.data.current_submission_form
        sf.acknowledged = choice
        sf.save()


class Resubmission(Activity):
    class Meta:
        model = Submission
        
    def get_url(self):
        return reverse('ecs.core.views.copy_latest_submission_form', kwargs={'submission_pk': self.workflow.data.pk})

class B2VoteReview(Activity):
    class Meta:
        model = Submission
        
    def get_url(self):
        return reverse('ecs.core.views.b2_vote_review', kwargs={'submission_form_pk': self.workflow.data.current_submission_form.pk})

class CategorizationReview(Activity):
    class Meta:
        model = Submission
        
    def is_repeatable(self):
        return True
        
    def get_url(self):
        return reverse('ecs.core.views.categorization_review', kwargs={'submission_form_pk': self.workflow.data.current_submission_form.pk})


class PaperSubmissionReview(Activity):
    class Meta:
        model = Submission
        
    def get_url(self):
        return reverse('ecs.core.views.readonly_submission_form', kwargs={'submission_form_pk': self.workflow.data.current_submission_form_id})


class ChecklistReview(Activity):
    class Meta:
        model = Submission
        vary_on = ChecklistBlueprint
        
    def is_reentrant(self):
        return False
        
    def is_locked(self):
        blueprint = self.node.data
        lookup_kwargs = {'blueprint': blueprint}
        if blueprint.multiple:
            lookup_kwargs['user'] = get_current_user()
        try:
            checklist = self.workflow.data.checklists.get(**lookup_kwargs)
        except Checklist.DoesNotExist:
            return False
        return not checklist.is_complete
        
    def get_url(self):
        blueprint = self.node.data
        submission_form = self.workflow.data.current_submission_form
        return reverse('ecs.core.views.checklist_review', kwargs={'submission_form_pk': submission_form.pk, 'blueprint_pk': blueprint.pk})

def unlock_checklist_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(ChecklistReview)
post_save.connect(unlock_checklist_review, sender=Checklist)


# XXX: This could be done without a Meta-class and without the additional signal handler if `ecs.workflow` properly supported activity inheritance. (FMD3)
class ExternalChecklistReview(ChecklistReview):
    class Meta:
        model = Submission
        vary_on = ChecklistBlueprint

    def receive_token(self, *args, **kwargs):
        token = super(ExternalChecklistReview, self).receive_token(*args, **kwargs)
        token.task.assign(self.workflow.data.external_reviewer_name)
        return token

def unlock_external_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(ExternalChecklistReview)
post_save.connect(unlock_external_review, sender=Checklist)


class ExternalReviewInvitation(Activity):
    class Meta:
        model = Submission
        
    def get_url(self):
        return None # FIXME: missing feature (FMD3)


class AdditionalReviewSplit(Generic):
    class Meta:
        model = Submission

    def emit_token(self, *args, **kwargs):
        tokens = []
        for user in self.workflow.data.additional_reviewers.all():
            for token in super(AdditionalReviewSplit, self).emit_token(*args, **kwargs):
                token.task.assign(user)
                tokens.append(token)
        return token

# XXX: This could be done without a Meta-class and without the additional signal handler if `ecs.workflow` properly supported activity inheritance. (FMD3)
class AdditionalChecklistReview(ChecklistReview):
    class Meta:
        model = Submission
        vary_on = ChecklistBlueprint
        
    def is_reentrant(self):
        return True

def unlock_additional_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(AdditionalChecklistReview)
post_save.connect(unlock_additional_review, sender=Checklist)


class VoteRecommendation(Activity):
    class Meta:
        model = Submission

    def get_url(self):
        return None # FIXME: missing feature (FMD3)


class VoteRecommendationReview(Activity):
    class Meta:
        model = Submission
        
    def get_url(self):
        return None # FIXME: missing feature (FMD3)


class VoteFinalization(Activity):
    class Meta:
        model = Vote
    
    def get_url(self):
        return reverse('ecs.core.views.vote_review', kwargs={'submission_form_pk': self.workflow.data.submission_form_id})


class VoteReview(Activity):
    class Meta:
        model = Vote
        
    def get_url(self):
        return reverse('ecs.core.views.vote_review', kwargs={'submission_form_pk': self.workflow.data.submission_form_id})


class VoteSigning(Activity):
    class Meta:
        model = Vote
        
    def get_url(self):
        return reverse('ecs.core.views.vote_sign', kwargs={'meeting_pk': self.workflow.data.top.meeting.pk, 'vote_pk': self.workflow.data.pk})


class VotePublication(Activity):
    class Meta:
        model = Vote

    def pre_perform(self, choice):
        vote = self.workflow.data
        vote.published_at = datetime.now()
        vote.save()

