from django.http import Http404, HttpResponse
from django.utils import simplejson
from django.contrib.auth.models import User, Group
from ecs.utils.countries.models import Country
from ecs.core.models import MedicalCategory, ExpeditedReviewCategory

AUTOCOMPLETE_QUERYSETS = {
    'countries': lambda: [(c.pk, "%s (%s)" % (c.printable_name, c.iso), c.printable_name) for c in Country.objects.order_by('name')],
    'medical_categories': lambda: [(str(c.pk), "%s (%s)" % (c.name, c.abbrev), c.name) for c in MedicalCategory.objects.order_by('name')],
    'expedited_review_categories': lambda: [(str(c.pk), "%s (%s)" % (c.name, c.abbrev), c.name) for c in ExpeditedReviewCategory.objects.order_by('name')],
    'users': lambda: [(str(u.pk), u.username, u.username) for u in User.objects.order_by('username')],
    'groups': lambda: [(str(u.pk), u.name, u.name) for u in Group.objects.order_by('name')],
}

def autocomplete(request, queryset_name=None):
    try:
        result = AUTOCOMPLETE_QUERYSETS[queryset_name]()
    except KeyError:
        raise Http404
    return HttpResponse(simplejson.dumps(result), content_type='application/json')
