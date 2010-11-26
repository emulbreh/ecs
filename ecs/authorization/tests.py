import datetime
from contextlib import contextmanager
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from ecs.utils.testcases import EcsTestCase
from ecs.core.tests.submissions import create_submission_form
from ecs.core.models import Submission
from ecs.meetings.models import Meeting
from ecs.users.utils import sudo

class SubmissionAuthTestCase(EcsTestCase):
    BASE_EC_NUMBER = 9742
    EC_NUMBER = 20100000 + BASE_EC_NUMBER

    def _create_test_user(self, name, **profile_attrs):
        user = User(username=name)
        user.set_password(name)
        user.save()
        profile = user.get_profile()
        for name, value in profile_attrs.items():
            setattr(profile, name, value)
        profile.save()
        return user
    
    def setUp(self):
        super(SubmissionAuthTestCase, self).setUp()
        self.additional_review_user = self._create_test_user('additional_review', approved_by_office=True)
        self.anyone = self._create_test_user('anyone', approved_by_office=True)
        self.board_member_user = self._create_test_user('board_member', approved_by_office=True, board_member=True)
        self.expedited_review_user = self._create_test_user('expedited_review', approved_by_office=True, expedited_review=True)
        self.external_review_user = self._create_test_user('external_review', approved_by_office=True, external_review=True)
        self.insurance_review_user = self._create_test_user('insurance_review', approved_by_office=True, insurance_review=True)
        self.internal_user = self._create_test_user('internal', approved_by_office=True, internal=True)
        self.primary_investigator_user = self._create_test_user('primary_investigator', approved_by_office=True)
        self.sponsor_user = self._create_test_user('sponsor', approved_by_office=True)
        self.submitter_user = self._create_test_user('submitter', approved_by_office=True)
        self.thesis_review_user = self._create_test_user('thesis_review', approved_by_office=True, thesis_review=True)
    
        self.another_board_member_user = self._create_test_user('another_board_member', approved_by_office=True, board_member=True)
        self.unapproved_user = self._create_test_user('unapproved_user')
    
        sf = create_submission_form()
        sf.submitter = self.submitter_user
        sf.sponsor = self.sponsor_user
        sf.additional_review_user = self.additional_review_user
        sf.project_title = self.EC_NUMBER
        sf.save()
    
        investigator = sf.investigators.all()[0]
        investigator.user = self.primary_investigator_user
        investigator.save()

        sf.submission.ec_number = self.EC_NUMBER
        sf.submission.additional_reviewers.add(self.additional_review_user)
        sf.submission.external_reviewer_name = self.external_review_user

        meeting = Meeting.objects.create(start=datetime.datetime.now())
        entry = meeting.add_entry(submission=sf.submission, duration_in_seconds=60)
        entry.add_user(self.board_member_user)
        sf.submission.next_meeting = meeting
        sf.submission.save()

        self.sf = sf
        
    def test_submission_auth(self):
        with sudo(self.unapproved_user):
            self.failUnlessEqual(Submission.objects.count(), 0)
        with sudo(self.anyone):
            self.failUnlessEqual(Submission.objects.count(), 0)
        with sudo(self.submitter_user):
            self.failUnlessEqual(Submission.objects.count(), 1)
        with sudo(self.sponsor_user):
            self.failUnlessEqual(Submission.objects.count(), 1)
        with sudo(self.primary_investigator_user):
            self.failUnlessEqual(Submission.objects.count(), 1)
        with sudo(self.additional_review_user):
            self.failUnlessEqual(Submission.objects.count(), 1)
        with sudo(self.internal_user):
            self.failUnlessEqual(Submission.objects.count(), 1)
        with sudo(self.external_review_user):
            self.failUnlessEqual(Submission.objects.count(), 1)
        with sudo(self.board_member_user):
            self.failUnlessEqual(Submission.objects.count(), 1)
        with sudo(self.another_board_member_user):
            self.failUnlessEqual(Submission.objects.count(), 0)

        with sudo(self.thesis_review_user):
            self.failUnlessEqual(Submission.objects.count(), 0)
        self.sf.submission.thesis = True
        self.sf.submission.save()
        with sudo(self.thesis_review_user):
            self.failUnlessEqual(Submission.objects.count(), 1)

        with sudo(self.expedited_review_user):
            self.failUnlessEqual(Submission.objects.count(), 0)
        self.sf.submission.expedited = True
        self.sf.submission.save()
        with sudo(self.thesis_review_user):
            self.failUnlessEqual(Submission.objects.count(), 1)
    
    @contextmanager
    def _login(self, user):
        self.client.login(username=user.username, password=user.username)
        yield
        self.client.logout()
        
    def _check_access(self, allowed, expect404, user, url):
        with self._login(user):
            response = self.client.get(url)
            while response.status_code == 302:
                response = self.client.get(response['Location'])
            if expect404:
                self.failUnlessEqual(response.status_code, allowed and 200 or 404)
            else:
                self.failUnlessEqual(str(self.BASE_EC_NUMBER) in response.content, allowed)
                
    def _check_view(self, expect404, viewname, *args, **kwargs):
        url = reverse(viewname, args=args, kwargs=kwargs)
        self._check_access(False, expect404, self.unapproved_user, url)
        self._check_access(False, expect404, self.anyone, url)
        self._check_access(False, expect404, self.anyone, url)
        self._check_access(True, expect404, self.submitter_user, url)
        self._check_access(True, expect404, self.sponsor_user, url)
        self._check_access(True, expect404, self.primary_investigator_user, url)
        self._check_access(True, expect404, self.additional_review_user, url)
        self._check_access(True, expect404, self.internal_user, url)
        self._check_access(True, expect404, self.external_review_user, url)
        self._check_access(True, expect404, self.board_member_user, url)
        self._check_access(False, expect404, self.another_board_member_user, url)

    def test_views(self):
        self._check_view(False, 'ecs.core.views.submission_forms')
        self._check_view(False, 'ecs.core.views.readonly_submission_form', submission_form_pk=self.sf.pk)
        self._check_view(True, 'ecs.core.views.submission_pdf', submission_form_pk=self.sf.pk)
        self._check_view(True, 'ecs.core.views.export_submission', submission_pk=self.sf.submission.pk)
        self._check_view(False, 'ecs.core.views.diff', self.sf.pk, self.sf.pk)

        #self._check_view(True, 'ecs.documents.views.document_search', document_pk=self.sf.documents.all()[0].pk)
        #self._check_view(True, 'ecs.documents.views.download_document', document_pk=self.sf.documents.all()[0].pk)
        #self._check_view('ecs.core.views.retrospective_thesis_review', submission_form_pk=self.sf.pk)
        #self._check_view('ecs.core.views.copy_submission_form', submission_form_pk=self.sf.pk)
        #self._check_view('ecs.core.views.copy_latest_submission_form', submission_pk=self.sf.submission.pk)
        
