# -*- coding: utf-8 -*-
from django.contrib import admin

from ecs.core.models import ChecklistBlueprint, ChecklistQuestion, Checklist, ChecklistAnswer
from ecs.core.models import EthicsCommission, SubmissionForm, Investigator
from ecs.core.models import InvestigatorEmployee, Measure, NonTestedUsedDrug
from ecs.core.models import ForeignParticipatingCenter
from ecs.core.models import Submission, MedicalCategory


# Nicer Checklist Editing
class ChecklistQuestionInline(admin.TabularInline):
    model = ChecklistQuestion

class ChecklistBlueprintAdmin(admin.ModelAdmin):
    inlines = [
        ChecklistQuestionInline,
    ]


class ChecklistAnswerInline(admin.TabularInline):
    model = ChecklistAnswer

class ChecklistAdmin(admin.ModelAdmin):
    inlines = [
        ChecklistAnswerInline,
    ]


admin.site.register(ChecklistBlueprint, ChecklistBlueprintAdmin)
admin.site.register(ChecklistQuestion)
admin.site.register(Checklist, ChecklistAdmin)
admin.site.register(ChecklistAnswer)
admin.site.register(EthicsCommission)
admin.site.register(SubmissionForm)
admin.site.register(Investigator)
admin.site.register(InvestigatorEmployee)
admin.site.register(Measure)
admin.site.register(NonTestedUsedDrug)
admin.site.register(ForeignParticipatingCenter)
admin.site.register(Submission)
admin.site.register(MedicalCategory)
