# -*- coding: utf-8 -*-
import re
from django.template import Library
from django.utils.safestring import mark_safe

from ecs.core import paper_forms

register = Library()

def getitem(obj, name):
    try:
        return obj[name]
    except KeyError:
        return None

register.filter('getattr', lambda obj, name: getattr(obj, str(name)))
register.filter('getitem', getitem)
register.filter('type_name', lambda obj: type(obj).__name__)
register.filter('startwith', lambda obj, start: obj.startswith(substr))
register.filter('endswith', lambda obj, end: obj.endswith(end))
register.filter('contains', lambda obj, x: x in obj)
register.filter('not', lambda obj: not obj)
register.filter('multiply', lambda a, b: a * b)
register.filter('euro', lambda val: (u"€ %.2f" % float(val)).replace('.', ','))

@register.filter
def ec_number(submission):
    if submission:
        return submission.get_ec_number_display()
    return None

@register.filter
def repeat(s, n):
    return mark_safe(s*n)
repeat.is_safe = True

@register.filter
def get_field_info(formfield):
    if formfield and hasattr(formfield.form, '_meta'):
        return paper_forms.get_field_info(model=formfield.form._meta.model, name=formfield.name)
    else:
        return None

@register.filter
def id_for_label(field):
    widget = field.field.widget
    id_ = widget.attrs.get('id') or field.auto_id
    return widget.id_for_label(id_)

@register.filter
def form_value(form, fieldname):
    if form.data:
        return form._raw_value(fieldname)
    try:
        return form.initial[fieldname]
    except KeyError:
        return None
        
@register.filter
def simple_timedelta_format(td):
    if not td.seconds:
        return "0"
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    result = []
    if hours:
        result.append("%sh" % hours)
    if minutes:
        result.append("%smin" % minutes)
    if seconds:
        result.append("%ss" % seconds)
    return " ".join(result)
    
@register.filter
def smart_truncate(s, n):
    if not s:
        return u""
    if len(s) <= n:
        return s
    return u"%s …" % re.match(r'(.{,%s})\b' % (n - 2), s).group(0)
    

@register.filter
def class_for_field(field):
    return 'wide' if field.field.max_length > 50 else 'narrow'

