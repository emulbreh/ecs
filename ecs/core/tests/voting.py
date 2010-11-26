# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from django.conf import settings

from ecs.communication.testcases import CommunicationTestCase
from ecs.core.tests.submissions import create_submission_form
from ecs.core.task_queue import send_reminder_messages
from ecs.meetings.models import Meeting
from ecs.core.models import Vote
from ecs.communication.models import Message

class VoteRemindersTest(CommunicationTestCase):
    def setUp(self, *args, **kwargs):
        rval = super(VoteRemindersTest, self).setUp(*args, **kwargs)

        # alice is the submitter and bob is the postmaster
        settings.ECSMAIL['postmaster'] = 'bob'

        # there has to be a test submission
        self.submission_form = create_submission_form()
        self.submission_form.submission.thesis = False
        self.submission_form.submission.save()
        self.submission_form.project_type_education_context = None
        self.submission_form.submitter_email = self.alice.email
        self.submission_form.save()

        self.submission_form_thesis = create_submission_form()
        self.submission_form_thesis.submission.thesis = True
        self.submission_form_thesis.submitter_email = self.alice.email
        self.submission_form_thesis.submission.save()

        self.january_meeting = Meeting.objects.create(title='January Meeting', start=datetime(2042, 1, 1))
        self.february_meeting = Meeting.objects.create(title='February Meeting', start=datetime(2042, 2, 1))
        self.march_meeting = Meeting.objects.create(title='March Meeting', start=datetime(2042, 3, 1))
        self.april_meeting = Meeting.objects.create(title='April Meeting', start=datetime(2042, 4, 1))

        for meeting in (self.january_meeting, self.february_meeting, self.march_meeting, self.april_meeting):
            meeting.started = meeting.start
            meeting.ended = meeting.start + timedelta(hours=8)
            meeting.deadline = meeting.start - timedelta(days=7)
            meeting.deadline_diplomathesis = meeting.start - timedelta(days=2)
            meeting.save()

        self.january_meeting.add_entry(submission=self.submission_form.submission, duration_in_seconds=60)
        self.january_meeting.add_entry(submission=self.submission_form_thesis.submission, duration_in_seconds=60)

        self.vote = Vote.objects.create(submission_form=self.submission_form, top=self.january_meeting.timetable_entries.get(submission=self.submission_form.submission), result='2')
        self.vote_thesis = Vote.objects.create(submission_form=self.submission_form_thesis, top=self.january_meeting.timetable_entries.get(submission=self.submission_form_thesis), result='2')

        return rval

    def test_expiry(self):
        alice_message_count = Message.objects.filter(receiver=self.alice).count()
        bob_message_count = Message.objects.filter(receiver=self.bob).count()
        send_reminder_messages(today=(self.april_meeting.deadline+timedelta(days=1)).date())
        self.failUnless(alice_message_count < Message.objects.filter(receiver=self.alice).count())
        self.failUnless(bob_message_count < Message.objects.filter(receiver=self.bob).count())

    def test_expiry_diplomathesis(self):
        alice_message_count = Message.objects.filter(receiver=self.alice).count()
        bob_message_count = Message.objects.filter(receiver=self.bob).count()
        send_reminder_messages(today=(self.april_meeting.deadline_diplomathesis+timedelta(days=1)).date())
        self.failUnless(alice_message_count < Message.objects.filter(receiver=self.alice).count())
        self.failUnless(bob_message_count < Message.objects.filter(receiver=self.bob).count())

    def test_reminder_office(self):
        message_count = Message.objects.filter(receiver=self.bob).count()
        send_reminder_messages(today=(self.april_meeting.deadline-timedelta(days=7)).date())
        self.failUnless(message_count < Message.objects.filter(receiver=self.bob).count())

    def test_reminder_office_diplomathesis(self):
        message_count = Message.objects.filter(receiver=self.bob).count()
        send_reminder_messages(today=(self.april_meeting.deadline_diplomathesis-timedelta(days=7)).date())
        self.failUnless(message_count < Message.objects.filter(receiver=self.bob).count())

    def test_reminder_submitter(self):
        message_count = Message.objects.filter(receiver=self.alice).count()
        send_reminder_messages(today=(self.april_meeting.deadline-timedelta(days=21)).date())
        self.failUnless(message_count < Message.objects.filter(receiver=self.alice).count())

    def test_reminder_submitter_diplomathesis(self):
        message_count = Message.objects.filter(receiver=self.alice).count()
        send_reminder_messages(today=(self.april_meeting.deadline_diplomathesis-timedelta(days=21)).date())
        self.failUnless(message_count < Message.objects.filter(receiver=self.alice).count())

