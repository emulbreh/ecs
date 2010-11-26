# -*- coding: utf-8 -*-
import os, random
from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import CommandError
from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType
from django.core.files import File

from ecs import bootstrap
from ecs.core.models import ExpeditedReviewCategory, Submission, MedicalCategory, EthicsCommission, ChecklistBlueprint, ChecklistQuestion, Investigator, SubmissionForm, Checklist, ChecklistAnswer
from ecs.notifications.models import NotificationType
from ecs.utils.countries.models import Country
from ecs.utils import Args
from ecs.users.utils import sudo
from ecs.documents.models import Document, DocumentType
from ecs.workflow.patterns import Generic
from ecs.integration.utils import setup_workflow_graph


@bootstrap.register()
def default_site():
    # default_site is needed for dbtemplates
    Site.objects.get_or_create(pk=1)

@bootstrap.register(depends_on=('ecs.core.bootstrap.default_site',))
def templates():
    from dbtemplates.models import Template
    basedir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    for dirpath, dirnames, filenames in os.walk(basedir):
        if 'xhtml2pdf' not in dirpath:
            continue
        for filename in filenames:
            if filename.startswith('.'):
                continue
            _, ext = os.path.splitext(filename)
            if ext in ('.html', '.inc'):
                path = os.path.join(dirpath, filename)
                name = "db%s" % path.replace(basedir, '').replace('\\', '/')
                content = open(path, 'r').read()
                tpl, created = Template.objects.get_or_create(name=name, defaults={'content': content})
                if not created and tpl.last_changed < datetime.fromtimestamp(os.path.getmtime(path)):
                    tpl.content = content
                    tpl.save()

@bootstrap.register(depends_on=('ecs.integration.bootstrap.workflow_sync', 'ecs.core.bootstrap.checklist_blueprints'))
def submission_workflow():
    from ecs.core.models import Submission
    from ecs.core.workflow import (InitialReview, Resubmission, CategorizationReview, PaperSubmissionReview, AdditionalReviewSplit, AdditionalChecklistReview,
        ChecklistReview, ExternalChecklistReview, ExternalReviewInvitation, VoteRecommendation, VoteRecommendationReview, B2VoteReview)
    from ecs.core.workflow import is_acknowledged, is_thesis, is_expedited, has_recommendation, has_accepted_recommendation, has_b2vote, needs_external_review
    
    statistical_review_checklist_blueprint = ChecklistBlueprint.objects.get(slug='statistic_review')
    insurance_review_checklist_blueprint = ChecklistBlueprint.objects.get(slug='insurance_review')
    legal_and_patient_review_checklist_blueprint = ChecklistBlueprint.objects.get(slug='legal_review')
    boardmember_review_checklist_blueprint = ChecklistBlueprint.objects.get(slug='boardmember_review')
    external_review_checklist_blueprint = ChecklistBlueprint.objects.get(slug='external_review')
    additional_review_checklist_blueprint = ChecklistBlueprint.objects.get(slug='additional_review')
    
    THESIS_REVIEW_GROUP = 'EC-Thesis Review Group'
    THESIS_EXECUTIVE_GROUP = 'EC-Thesis Executive Group'
    EXECUTIVE_GROUP = 'EC-Executive Board Group'
    PRESENTER_GROUP = 'Presenter'
    OFFICE_GROUP = 'EC-Office'
    BOARD_MEMBER_GROUP = 'EC-Board Member'
    EXTERNAL_REVIEW_GROUP = 'External Reviewer'
    INSURANCE_REVIEW_GROUP = 'EC-Insurance Reviewer'
    STATISTIC_REVIEW_GROUP = 'EC-Statistic Group'
    INTERNAL_REVIEW_GROUP = 'EC-Internal Review Group'
    
    setup_workflow_graph(Submission,
        auto_start=True,
        nodes={
            'start': Args(Generic, start=True, name="Start"),
            'generic_review': Args(Generic, name="Review Split"),
            'resubmission': Args(Resubmission, group=PRESENTER_GROUP),
            'initial_review': Args(InitialReview, group=OFFICE_GROUP),
            'b2_resubmission_review': Args(InitialReview, name="B2 Resubmission Review", group=INTERNAL_REVIEW_GROUP),
            'b2_vote_review': Args(B2VoteReview, group=OFFICE_GROUP),
            'categorization_review': Args(CategorizationReview, group=EXECUTIVE_GROUP),
            'additional_review_split': Args(AdditionalReviewSplit),
            'additional_review': Args(AdditionalChecklistReview, data=additional_review_checklist_blueprint, name=u"Additional Review"),
            'initial_thesis_review': Args(InitialReview, name="Initial Thesis Review", group=THESIS_REVIEW_GROUP),
            'thesis_categorization_review': Args(CategorizationReview, name="Thesis Categorization Review", group=THESIS_EXECUTIVE_GROUP),
            'paper_submission_review': Args(PaperSubmissionReview, group=OFFICE_GROUP),
            'legal_and_patient_review': Args(ChecklistReview, data=legal_and_patient_review_checklist_blueprint, name=u"Legal and Patient Review", group=INTERNAL_REVIEW_GROUP),
            'insurance_review': Args(ChecklistReview, data=insurance_review_checklist_blueprint, name=u"Insurance Review", group=INSURANCE_REVIEW_GROUP),
            'statistical_review': Args(ChecklistReview, data=statistical_review_checklist_blueprint, name=u"Statistical Review", group=STATISTIC_REVIEW_GROUP),
            'board_member_review': Args(ChecklistReview, data=boardmember_review_checklist_blueprint, name=u"Board Member Review", group=BOARD_MEMBER_GROUP),
            'external_review': Args(ExternalChecklistReview, data=external_review_checklist_blueprint, name=u"External Review", group=EXTERNAL_REVIEW_GROUP),
            'external_review_invitation': Args(ExternalReviewInvitation, group=OFFICE_GROUP),
            'thesis_vote_recommendation': Args(VoteRecommendation, group=THESIS_EXECUTIVE_GROUP),
            'vote_recommendation_review': Args(VoteRecommendationReview, group=EXECUTIVE_GROUP),
        },
        edges={
            ('start', 'initial_review'): Args(guard=is_thesis, negated=True),
            ('start', 'initial_thesis_review'): Args(guard=is_thesis),

            ('initial_review', 'resubmission'): Args(guard=is_acknowledged, negated=True),
            ('initial_review', 'categorization_review'): Args(guard=is_acknowledged),
            ('initial_review', 'paper_submission_review'): None,

            ('initial_thesis_review', 'resubmission'): Args(guard=is_acknowledged, negated=True),
            ('initial_thesis_review', 'thesis_categorization_review'): Args(guard=is_acknowledged),
            ('initial_thesis_review', 'paper_submission_review'): None,
            
            ('resubmission', 'start'): Args(guard=has_b2vote, negated=True),
            ('resubmission', 'b2_resubmission_review'): Args(guard=has_b2vote),
            ('b2_resubmission_review', 'b2_vote_review'): None,
            ('b2_vote_review', 'resubmission'): Args(guard=has_b2vote),

            ('thesis_categorization_review', 'thesis_vote_recommendation'): None,

            ('thesis_vote_recommendation', 'vote_recommendation_review'): Args(guard=has_recommendation),
            ('thesis_vote_recommendation', 'categorization_review'): Args(guard=has_recommendation, negated=True),

            #('vote_recommendation_review', 'END'): Args(guard=has_accepted_recommendation),
            ('vote_recommendation_review', 'categorization_review'): Args(guard=has_accepted_recommendation, negated=True),

            #('categorization_review', 'END'): Args(guard=is_expedited),
            ('categorization_review', 'generic_review'): Args(guard=is_expedited, negated=True),
            ('categorization_review', 'external_review_invitation'): Args(guard=needs_external_review),
            ('categorization_review', 'additional_review_split'): None,
            
            ('external_review_invitation', 'external_review'): None,
            ('external_review', 'external_review_invitation'): Args(deadline=True),
            ('additional_review_split', 'additional_review'): None,

            ('generic_review', 'board_member_review'): None,
            ('generic_review', 'insurance_review'): None,
            ('generic_review', 'statistical_review'): None,
            ('generic_review', 'legal_and_patient_review'): None,
        }
    )
    

@bootstrap.register(depends_on=('ecs.integration.bootstrap.workflow_sync', 'ecs.core.bootstrap.auth_groups'))
def vote_workflow():
    from ecs.core.models import Vote
    from ecs.core.workflow import VoteFinalization, VoteReview, VoteSigning, VotePublication
    from ecs.core.workflow import is_executive_vote_review_required, is_final, is_b2upgrade

    setup_workflow_graph(Vote, 
        auto_start=True, 
        nodes={
            'start': Args(Generic, start=True, name="Start"),
            'review': Args(Generic, name="Review Split"),
            'b2upgrade': Args(Generic, name="B2 Upgrade", end=True),
            'executive_vote_finalization': Args(VoteReview, name="Executive Vote Finalization"),
            'executive_vote_review': Args(VoteReview, name="Executive Vote Review"),
            'internal_vote_review': Args(VoteReview, name="Internal Vote Review"),
            'office_vote_finalization': Args(VoteReview, name="Office Vote Finalization"),
            'office_vote_review': Args(VoteReview, name="Office Vote Review"),
            'final_office_vote_review': Args(VoteReview, name="Office Vote Review"),
            'vote_signing': Args(VoteSigning),
            'vote_publication': Args(VotePublication, end=True),
        }, 
        edges={
            ('start', 'review'): Args(guard=is_b2upgrade, negated=True),
            ('start', 'b2upgrade'): Args(guard=is_b2upgrade),
            ('review', 'executive_vote_finalization'): Args(guard=is_executive_vote_review_required),
            ('review', 'office_vote_finalization'): Args(guard=is_executive_vote_review_required, negated=True),
            ('executive_vote_finalization', 'office_vote_review'): None,
            ('office_vote_finalization', 'internal_vote_review'): None,

            ('office_vote_review', 'executive_vote_review'): Args(guard=is_final, negated=True),
            ('office_vote_review', 'vote_signing'): Args(guard=is_final),

            ('internal_vote_review', 'office_vote_finalization'): Args(guard=is_final, negated=True),
            ('internal_vote_review', 'executive_vote_review'): Args(guard=is_final),

            ('executive_vote_review', 'final_office_vote_review'): Args(guard=is_final, negated=True),
            ('executive_vote_review', 'vote_signing'): Args(guard=is_final),
            
            ('final_office_vote_review', 'executive_vote_review'): None,
            ('vote_signing', 'vote_publication'): None
        }
    )


@bootstrap.register()
def auth_groups():
    groups = (
        u'Presenter',
        u'Sponsor',
        u'Investigator',
        u'EC-Office',
        u'EC-Meeting Secretary',
        u'EC-Internal Review Group',
        u'EC-Executive Board Group',
        u'EC-Signing Group',
        u'EC-Statistic Group',
        u'EC-Notification Review Group',
        u'EC-Insurance Reviewer',
        u'EC-Thesis Review Group',
        u'EC-Thesis Executive Group',
        u'EC-Board Member',
        u'External Reviewer',
        u'userswitcher_target',
    )
    for group in groups:
        Group.objects.get_or_create(name=group)


@bootstrap.register()
def notification_types():
    types = (
        (u"Nebenwirkungsmeldung (SAE/SUSAR Bericht)", "ecs.core.forms.NotificationForm"),
        (u"Protokolländerung", "ecs.core.forms.NotificationForm"),
        (u"Zwischenbericht", "ecs.core.forms.ProgressReportNotificationForm"),
        (u"Abschlussbericht", "ecs.core.forms.CompletionReportNotificationForm"),
    )
    
    for name, form in types:
        NotificationType.objects.get_or_create(name=name, form=form)

@bootstrap.register()
def expedited_review_categories():
    categories = (
        (u'KlPh', u'Klinische Pharmakologie'),
        (u'Stats', u'Statistik'),
        (u'Labor', u'Labormedizin'),
        (u'Recht', u'Juristen'),
        (u'Radio', u'Radiologie'),
        (u'Anästh', u'Anästhesie'),
        (u'Psychol', u'Psychologie'),
        (u'Patho', u'Pathologie'),
        (u'Zahn', u'Zahnheilkunde'),
        )
    for abbrev, name in categories:
        ExpeditedReviewCategory.objects.get_or_create(abbrev=abbrev, name=name)


@bootstrap.register()
def medical_categories():
    categories = (
        (u'Stats', u'Statistik'),
        (u'Pharma', u'Pharmakologie'), 
        (u'KlPh', u'Klinische Pharmakologie'),
        (u'Onko', u'Onkologie'),
        (u'Häm', u'Hämatologie'), 
        (u'Infektio', u'Infektiologie'),
        (u'Kardio', u'Kardiologie'),
        (u'Angio', u'Angiologie'),
        (u'Pulmo', u'Pulmologie'),
        (u'Endo', u'Endokrinologie'),
        (u'Nephro', u'Nephrologie'), 
        (u'Gastro', u'Gastroenterologie'),
        (u'Rheuma', u'Rheumatologie'),
        (u'Intensiv', u'Intensivmedizin'),
        (u'Chir', u'Chirugie'), 
        (u'plChir', u'Plastische Chirugie'),
        (u'HTChir', u'Herz-Thorax Chirugie'),
        (u'KiChir', u'Kinder Chirugie'),
        (u'NeuroChir', u'Neurochirurgie'),
        (u'Gyn', u'Gynäkologie'),
        (u'HNO', u'Hals-Nasen-Ohrenkrankheiten'),
        (u'Anästh', u'Anästhesie'),
        (u'Neuro', u'Neurologie'),
        (u'Psych', u'Psychatrie'),
        (u'Päd', u'Pädiatrie'),
        (u'Derma', u'Dermatologie'),
        (u'Radio', u'Radiologie'),
        (u'Transfus', u'Transfusionsmedizin'),
        (u'Ortho', u'Orthopädie'),
        (u'Uro', u'Urologie'), 
        (u'Notfall', u'Notfallmedizin'), 
        (u'PhysMed', u'Physikalische Medizin'),      
        (u'PsychAna', u'Psychoanalyse'),
        (u'Auge', u'Ophtalmologie'),
        (u'Nuklear', u'Nuklearmedizin'),
        (u'Labor', u'Labormedizin'),
        (u'Physiol', u'Physiologie'),
        (u'Anatomie', u'Anatomie'),
        (u'Zahn', u'Zahnheilkunde'),
        (u'ImmunPatho', u'Immunpathologie'),
        (u'Patho', u'Pathologie'),

        (u'Pfleger', u'Gesundheits und Krankenpfleger'),
        (u'Recht', u'Juristen'),
        (u'Pharmazie', u'Pharmazeuten'),
        (u'Patient', u'Patientenvertreter'), 
        (u'BehinOrg', u'Benhindertenorganisation'), 
        (u'Seel', u'Seelsorger'),
        (u'techSec', u'technischer Sicherheitsbeauftragter'),

        (u'LaborDia', u'medizinische und chemische Labordiagnostik'),
        (u'Psychol', u'Psychologie'), 
    )
    for shortname, longname in categories:
        medcat, created = MedicalCategory.objects.get_or_create(abbrev=shortname)
        medcat.name = longname
        medcat.save()

@bootstrap.register(depends_on=('ecs.core.bootstrap.auth_groups',))
def auth_user_developers():
    ''' Developer Account Creation '''
    try:
        from ecs.core.bootstrap_settings import developers
    except ImportError:
        developers = (('developer', u'John', u'Doe', u'developer@example.com', 'changeme'),)
    
    for dev in developers:
        user, created = User.objects.get_or_create(username=dev[0])
        user.first_name = dev[1]
        user.last_name = dev[2]
        user.email = dev[3]
        user.set_password(dev[4])
        user.is_staff = True
        user.groups.add(Group.objects.get(name="Presenter"))
        user.save()
        profile = user.get_profile()
        profile.approved_by_office = True
        profile.save()
        
        

@bootstrap.register(depends_on=('ecs.core.bootstrap.auth_groups', 
    'ecs.core.bootstrap.expedited_review_categories', 'ecs.core.bootstrap.medical_categories'))
def auth_user_testusers():
    ''' Test User Creation, target to userswitcher'''
    testusers = (
        (u'Presenter', u'Presenter',{'approved_by_office': True}),
        (u'Sponsor', u'Sponsor', {'approved_by_office': True}),
        (u'Investigtor', u'Investigator', {'approved_by_office': True}),
        (u'Office', u'EC-Office', {'internal': True, 'approved_by_office': True}),
        (u'Meeting Secretary', u'EC-Meeting Secretary',
            {'internal': True, 'approved_by_office': True}),
        (u'Internal Rev', u'EC-Internal Review Group',
            {'internal': True, 'approved_by_office': True}),
        (u'Executive', u'EC-Executive Board Group',             
            {'internal': True, 'executive_board_member': True, 'approved_by_office': True}),
        (u'Signing', u'EC-Signing Group',                       
            {'internal': True, 'approved_by_office': True}),
        (u'Statistic Rev', u'EC-Statistic Group',
            {'internal': True, 'approved_by_office': True}),
        (u'Notification Rev', u'EC-Notification Review Group',
            {'internal': True, 'approved_by_office': True}),
        (u'Insurance Rev', u'EC-Insurance Reviewer',            
            {'internal': False, 'approved_by_office': True}),
        (u'Thesis Rev', u'EC-Thesis Review Group',              
            {'internal': False, 'thesis_review': True, 'approved_by_office': True}),
        (u'External Reviewer', u'External Reviewer',            
            {'external_review': True, 'approved_by_office': True}),
    )
        
    boardtestusers = (
         (u'B.Member 1 (KlPh)', ('KlPh',)),
         (u'B.Member 2 (KlPh, Onko)', ('KlPh','Onko')),
         (u'B.Member 3 (Onko)', ('Onko',)),
         (u'B.Member 4 (Infektio)', ('Infektio',)),
         (u'B.Member 5 (Kardio)', ('Kardio',)),
         (u'B.Member 6 (Päd)', ('Päd',)), 
    )
    
    for testuser, testgroup, flags in testusers:
        for number in range(1,4):
            user, created = User.objects.get_or_create(username=" ".join((testuser,str(number))))
            user.groups.add(Group.objects.get(name=testgroup))
            user.groups.add(Group.objects.get(name="userswitcher_target"))

            profile = user.get_profile()
            for flagname, flagvalue in flags.items():
                setattr(profile, flagname, flagvalue)
            profile.save()
    
    for testuser, medcategories in boardtestusers:
        user, created = User.objects.get_or_create(username=testuser)
        user.groups.add(Group.objects.get(name='EC-Board Member'))
        user.groups.add(Group.objects.get(name="userswitcher_target"))

        profile = user.get_profile()
        profile.board_member = True
        profile.approved_by_office = True
        profile.save()

        for medcategory in medcategories:
            m= MedicalCategory.objects.get(abbrev=medcategory)
            m.users.add(user)
            try:
                e= ExpeditedReviewCategory.objects.get(abbrev=medcategory)
                e.users.add(user)
            except ObjectDoesNotExist:
                pass

@bootstrap.register(depends_on=('ecs.core.bootstrap.auth_groups',))
def auth_ec_staff_users():
    try:
        from ecs.core.bootstrap_settings import staff_users
    except ImportError:
        staff_users = (('staff', u'Staff', u'User', u'staff@example.com', 'changeme', ('EC-Office', 'EC-Meeting Secretary',), {}),)

    for username, first, last, email, password, groups, flags in staff_users:
        user, created = User.objects.get_or_create(username=username[:30])
        user.first_name = first
        user.last_name = last
        user.email = email
        user.set_password(password)
        user.is_staff = True
        user.save()

        for group in groups:
            user.groups.add(Group.objects.get(name=group))
        profile = user.get_profile()

        flags['internal'] = True
        flags['approved_by_office'] = True
        for flagname, flagvalue in flags.items():
            profile.__setattr__(flagname, flagvalue)
        profile.save()
      
@bootstrap.register(depends_on=('ecs.core.bootstrap.auth_groups',
    'ecs.core.bootstrap.expedited_review_categories', 'ecs.core.bootstrap.medical_categories'))
def auth_ec_other_users():
    try:
        from ecs.core.bootstrap_settings import other_users
    except ImportError:
        other_users = (('other', u'Other', u'User', u'other@example.com', 'changeme', ('EC-Statistic Group',)),)

    for username, first, last, email, password, groups in other_users:
        user, created = User.objects.get_or_create(username=username[:30])
        if created:
            user.first_name = first
            user.last_name = last
            user.email = email
            user.set_password(password)
        user.save()
        for group in groups:
            user.groups.add(Group.objects.get(name=group))

@bootstrap.register(depends_on=('ecs.core.bootstrap.auth_groups',
    'ecs.core.bootstrap.expedited_review_categories', 'ecs.core.bootstrap.medical_categories'))
def auth_ec_boardmember_users():
    try:
        from ecs.core.bootstrap_settings import board_members
    except ImportError:
        board_members = (('boardmember', u'Board', u'Member', u'boardmember@example.com', 'changeme', ('Pharma',)),)

    board_member_group = Group.objects.get(name=u'EC-Board Member')
    for username, first, last, email, password, medcategories in board_members:
        user, created = User.objects.get_or_create(username=username[:30])
        user.first_name = first
        user.last_name = last
        user.email = email
        user.set_password(password)
        user.save()
        user.groups.add(board_member_group)

        for medcategory in medcategories:
            m= MedicalCategory.objects.get(abbrev=medcategory)
            m.users.add(user)
            try:
                e= ExpeditedReviewCategory.objects.get(abbrev=medcategory)
                e.users.add(user)
                user.ecs_profile.expedited_review = True
            except ObjectDoesNotExist:
                pass
            
        user.ecs_profile.board_member = True
        user.ecs_profile.save()

@bootstrap.register()
def ethics_commissions():
    try:
        from ecs.core.bootstrap_settings import commissions
    except ImportError:
        commissions = [{
            'uuid': u'12345678909876543212345678909876',
            'city': u'Neverland',
            'fax': None,
            'chairperson': None,
            'name': u'Ethikkomission von Neverland',
            'url': None,
            'email': None,
            'phone': None,
            'address_1': u'Mainstreet 1',
            'contactname': None,
            'address_2': u'',
            'zip_code': u'4223',
        }]

    for comm in commissions:
        ec, created = EthicsCommission.objects.get_or_create(uuid=comm['uuid'])
        for key in comm.keys():
            setattr(ec, key, comm[key])
        ec.save()

@bootstrap.register()
def checklist_blueprints():
    blueprints = (
        dict(slug='statistic_review', name=u'Statistik', min_document_count=0),
        dict(slug='legal_review', name=u'Legal and Patient Review'),
        dict(slug='insurance_review', name=u'Insurance Review'),
        dict(slug='boardmember_review', name=u'Board Member Review', multiple=True),
        dict(slug='external_review', name=u'External Review', min_document_count=1, multiple=True),
        dict(slug='additional_review', name=u'Additional Review', min_document_count=0, multiple=True),
    )
    
    for blueprint in blueprints:
        b, _ = ChecklistBlueprint.objects.get_or_create(slug=blueprint['slug'])
        changed = False
        for name, value in blueprint.items():
            if getattr(b, name) != value:
                setattr(b, name, value)
                changed = True
        if changed:
            b.save()

@bootstrap.register(depends_on=('ecs.core.bootstrap.checklist_blueprints',))
def checklist_questions():
    questions = {
        u'statistic_review': (
            u'1. Ist das Studienziel ausreichend definiert?',
            u'2. Ist das Design der Studie geeignet, das Studienziel zu erreichen?',
            u'3. Ist die Studienpopulation ausreichend definiert?',
            u'4. Sind die Zielvariablen geeignet definiert?',
            u'5. Ist die statistische Analyse beschrieben, und ist sie adäquat?',
            u'6. Ist die Größe der Stichprobe ausreichend begründet?',
        ),
        u'legal_review': (u"42 ?",),
        u'insurance_review': (u"42 ?",),
        u'boardmember_review': (u"42 ?",),
        u'external_review': (u"42 ?",),
        u'additional_review': (u"42 ?",),
    }

    for slug in questions.keys():
        blueprint = ChecklistBlueprint.objects.get(slug=slug)
        for q in questions[slug]:
            cq, created = ChecklistQuestion.objects.get_or_create(text=q, blueprint=blueprint)

@bootstrap.register(depends_on=('ecs.core.bootstrap.checklist_questions', 'ecs.core.bootstrap.medical_categories', 'ecs.core.bootstrap.ethics_commissions', 'ecs.core.bootstrap.auth_user_testusers', 'ecs.documents.bootstrap.document_types',))
def testsubmission():
    if Submission.objects.filter(ec_number=20104321):
        return
    submission, created = Submission.objects.get_or_create(ec_number=20104321)
    submission.medical_categories.add(MedicalCategory.objects.get(abbrev=u'Päd'))
    
    try:
        from ecs.core.bootstrap_settings import test_submission_form
    except ImportError:
        test_submission_form = {
            'acknowledged': False,
            'additional_therapy_info': u'',
            'already_voted': False,
            'clinical_phase': u'Neu',
            'created_at': datetime(2010, 11, 24, 18, 19, 13, 842468),
            'date_of_receipt': None,
            'eudract_number': u'',
            'external_reviewer_suggestions': u'',
            'german_abort_info': u'blabla',
            'german_additional_info': u'',
            'german_aftercare_info': u'blabla',
            'german_benefits_info': u'blabla',
            'german_concurrent_study_info': u'blabla',
            'german_consent_info': u'blabla',
            'german_dataaccess_info': u'',
            'german_dataprotection_info': u'',
            'german_ethical_info': u'blabla',
            'german_financing_info': u'',
            'german_inclusion_exclusion_crit': u'blabla',
            'german_payment_info': u'blabla',
            'german_preclinical_results': u'blabla',
            'german_primary_hypothesis': u'blabla',
            'german_project_title': u'Implantierung von Telefonen ins Ohr',
            'german_protected_subjects_info': u'blabla',
            'german_recruitment_info': u'blabla',
            'german_relationship_info': u'blabla',
            'german_risks_info': u'blabla',
            'german_sideeffects_info': u'blabla',
            'german_statistical_info': u'',
            'german_summary': u'blabla',
            'insurance_address': u'',
            'insurance_contract_number': u'',
            'insurance_name': u'',
            'insurance_phone': u'',
            'insurance_validity': u'',
            'invoice_address': u'',
            'invoice_city': u'',
            'invoice_contact_first_name': u'',
            'invoice_contact_gender': None,
            'invoice_contact_last_name': u'',
            'invoice_contact_title': u'',
            'invoice_email': u'',
            'invoice_fax': u'',
            'invoice_name': u'',
            'invoice_phone': u'',
            'invoice_uid': None,
            'invoice_uid_verified_level1': None,
            'invoice_uid_verified_level2': None,
            'invoice_zip_code': u'',
            'medtech_ce_symbol': None,
            'medtech_certified_for_exact_indications': None,
            'medtech_certified_for_other_indications': None,
            'medtech_checked_product': u'',
            'medtech_departure_from_regulations': u'',
            'medtech_manual_included': None,
            'medtech_manufacturer': u'',
            'medtech_product_name': u'',
            'medtech_reference_substance': u'',
            'medtech_technical_safety_regulations': u'',
            'pdf_document_id': None,
            'pharma_checked_substance': u'',
            'pharma_reference_substance': u'',
            'primary_investigator_id': None,
            'project_title': u'Implementation of phones into the ear',
            'project_type_basic_research': True,
            'project_type_biobank': False,
            'project_type_education_context': None,
            'project_type_genetic_study': False,
            'project_type_medical_device': False,
            'project_type_medical_device_performance_evaluation': False,
            'project_type_medical_device_with_ce': False,
            'project_type_medical_device_without_ce': False,
            'project_type_medical_method': True,
            'project_type_misc': u'',
            'project_type_non_reg_drug': False,
            'project_type_psychological_study': False,
            'project_type_questionnaire': False,
            'project_type_reg_drug': False,
            'project_type_reg_drug_not_within_indication': False,
            'project_type_reg_drug_within_indication': False,
            'project_type_register': False,
            'project_type_retrospective': False,
            'protocol_number': u'',
            'specialism': u'Chirurgie',
            'sponsor_address': u'main-street 1',
            'sponsor_agrees_to_publishing': True,
            'sponsor_city': u'Wien',
            'sponsor_contact_first_name': u'John',
            'sponsor_contact_gender': u'm',
            'sponsor_contact_last_name': u'Doe',
            'sponsor_contact_title': u'Dr.',
            'sponsor_email': u'johndoe@example.com',
            'sponsor_fax': u'',
            'sponsor_id': None,
            'sponsor_name': u'John Doe',
            'sponsor_phone': u'+43098765432123456789',
            'sponsor_zip_code': u'4223',
            'study_plan_abort_crit': u'blabla',
            'study_plan_alpha': u'blabla',
            'study_plan_alternative_hypothesis': u'',
            'study_plan_biometric_planning': u'blabla',
            'study_plan_blind': 0,
            'study_plan_controlled': False,
            'study_plan_cross_over': True,
            'study_plan_datamanagement': u'blabla',
            'study_plan_dataprotection_anonalgoritm': u'',
            'study_plan_dataprotection_dvr': u'',
            'study_plan_dataprotection_reason': u'',
            'study_plan_dataquality_checking': u'blabla',
            'study_plan_dropout_ratio': u'blabla',
            'study_plan_equivalence_testing': False,
            'study_plan_factorized': True,
            'study_plan_misc': u'',
            'study_plan_multiple_test_correction_algorithm': u'blabla',
            'study_plan_null_hypothesis': u'',
            'study_plan_number_of_groups': u'',
            'study_plan_observer_blinded': False,
            'study_plan_parallelgroups': False,
            'study_plan_pilot_project': False,
            'study_plan_placebo': False,
            'study_plan_planned_statalgorithm': u'',
            'study_plan_population_intention_to_treat': False,
            'study_plan_population_per_protocol': False,
            'study_plan_power': u'blabla',
            'study_plan_primary_objectives': u'',
            'study_plan_randomized': True,
            'study_plan_sample_frequency': u'',
            'study_plan_secondary_objectives': u'',
            'study_plan_statalgorithm': u'blabla',
            'study_plan_statistics_implementation': u'blabla',
            'study_plan_stratification': u'',
            'subject_childbearing': False,
            'subject_count': 4223,
            'subject_duration': u'2 monate',
            'subject_duration_active': u'jetzt',
            'subject_duration_controls': u'nie',
            'subject_females': True,
            'subject_males': True,
            'subject_maxage': 68,
            'subject_minage': 18,
            'subject_noncompetents': False,
            'subject_planned_total_duration': u'ohne ende',
            'submission_type': None,
            'submitter_contact_first_name': u'John',
            'submitter_contact_gender': u'm',
            'submitter_contact_last_name': u'Doe',
            'submitter_contact_title': u'',
            'submitter_email': u'developer@example.com',
            'submitter_id': 2,
            'submitter_is_authorized_by_sponsor': False,
            'submitter_is_coordinator': False,
            'submitter_is_main_investigator': False,
            'submitter_is_sponsor': False,
            'submitter_jobtitle': u'developer',
            'submitter_organisation': u'open source community',
            'substance_p_c_t_application_type': u'',
            'substance_p_c_t_final_report': None,
            'substance_p_c_t_gcp_rules': None,
            'substance_p_c_t_period': u'',
            'substance_p_c_t_phase': u'',
            'substance_preexisting_clinical_tries': None
        }
    
    patienteninformation_filename = os.path.join(os.path.dirname(__file__), 'tests', 'data', 'menschenrechtserklaerung.pdf')
    with open(patienteninformation_filename, 'rb') as patienteninformation:
        doctype = DocumentType.objects.get(identifier='patientinformation')
        doc = Document.objects.create_from_buffer(patienteninformation.read(), version='1', doctype=doctype, date=datetime.now())
        doc.save()

    test_submission_form['submission'] = submission
    test_submission_form['presenter'] = User.objects.get(username='Presenter 1')
    submission_form = SubmissionForm.objects.create(**test_submission_form)

    doc.parent_object = submission_form
    doc.save()
    
