# encoding: utf-8

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


# work around for pre Django 1.2

@register.filter
def less(x, y):
    return x < y

@register.filter
def greater(x, y):
    return x > y


# intergalactic translator

types_de = {
    'i': (u'Ihre', u'Idee', u'Ideen', u'Ihrer Idee', u'Keine'),
    'q': (u'Ihre', u'Frage', u'Fragen', u'Ihrer Frage', u'Keine'),
    'p': (u'Ihr', u'Problem', u'Probleme', u'Ihres Problems', u'Keine'),
    'l': (u'Ihr', u'Lob', u'Lob', u'Ihres Lobs', u'Kein')
}

types_de_whatever = (u'Ihr', u'Irgendwas', u'Irgendwas', u'Ihres Irgendwas', u'Kein')

@register.filter
@stringfilter
def fb_type_your(type):
    return types_de.get(type, types_de_whatever)[0]

@register.filter
@stringfilter
def fb_type(type):
    return types_de.get(type, types_de_whatever)[1]

@register.filter
@stringfilter
def fb_type_many(type):
    return types_de.get(type, types_de_whatever)[2]

@register.filter
@stringfilter
def fb_type_of_your(type):
    return types_de.get(type, types_de_whatever)[3]

@register.filter
@stringfilter
def fb_type_none(type):
    return types_de.get(type, types_de_whatever)[4]


@register.filter
def fb_type_items(type, items):
    if items == 1:
        return fb_type(type)
    else:
        return fb_type_many(type)


motivation_de = {
    'i': u'Teilen Sie Ihre Idee mit',
    'q': u'Stellen Sie Ihre Frage',
    'p': u'Beschreiben Sie Ihr Problem',
    'l': u'Geben Sie Lob'
}

@register.filter
@stringfilter
def fb_motivate(type):
    return motivation_de.get(type, u'Uh oh, da geht gerade etwas schief ..')


others_de = {
    (0, 'yours', 'i'): u'Sie haben diese Idee beschrieben',
    (0, 'u2',    'i'): u'Sie und Sie haben diese Idee beschrieben ?WTF',
    (0, 'me2',   'i'): u'Eine Person hat diese Idee beschrieben',
    (1, 'yours', 'i'): u'Einer weiteren Person gefällt Ihre Idee',
    (1, 'u2',    'i'): u'Einer Person und Ihnen gefällt diese Idee',
    (1, 'me2',   'i'): u'2 Personen gefällt diese Idee',
    (2, 'yours', 'i'): u'%s weiteren Personen gefällt Ihre Idee',
    (2, 'u2',    'i'): u'%s Personen und Ihnen gefällt diese Idee',
    (2, 'me2',   'i'): u'%s Personen gefällt diese Idee',

    (0, 'yours', 'q'): u'Sie haben diese Frage beschrieben',
    (0, 'u2',    'q'): u'Sie und Sie haben diese Frage beschrieben ?WTF',
    (0, 'me2',   'q'): u'Eine Person hat diese Frage beschrieben',
    (1, 'yours', 'q'): u'Eine weitere Person hat ebenfalls Ihre Frage',
    (1, 'u2',    'q'): u'Eine Person und Sie haben diese Frage',
    (1, 'me2',   'q'): u'2 Personen haben diese Frage',
    (2, 'yours', 'q'): u'%s weitere Personen haben ebenfalls Ihre Frage',
    (2, 'u2',    'q'): u'%s Personen und Sie haben diese Frage',
    (2, 'me2',   'q'): u'%s Personen haben diese Frage',

    (0, 'yours', 'p'): u'Sie haben dieses Problem beschrieben',
    (0, 'u2',    'p'): u'Sie und Sie haben dieses Problem beschrieben ?WTF',
    (0, 'me2',   'p'): u'Eine Person hat dieses Problem beschrieben',
    (1, 'yours', 'p'): u'Eine weitere Person hat ebenfalls Ihr Problem',
    (1, 'u2',    'p'): u'Eine Person und Sie haben dieses Problem',
    (1, 'me2',   'p'): u'2 Personen haben dieses Problem',
    (2, 'yours', 'p'): u'%s weitere Personen haben ebenfalls Ihr Problem',
    (2, 'u2',    'p'): u'%s Personen und Sie haben dieses Problem',
    (2, 'me2',   'p'): u'%s Personen haben dieses Problem',

    (0, 'yours', 'l'): u'Sie haben dieses Lob ausgesprochen',
    (0, 'u2',    'l'): u'Sie und Sie haben dieses Lob ausgesprochen ?WTF',
    (0, 'me2',   'l'): u'Eine Person hat dieses Lob ausgesprochen',
    (1, 'yours', 'l'): u'Eine weitere Person hat sich Ihrem Lob angeschlossen',
    (1, 'u2',    'l'): u'Eine Person und Sie haben dieses Lob ausgesprochen',
    (1, 'me2',   'l'): u'2 Personen haben dieses Lob ausgesprochen',
    (2, 'yours', 'l'): u'%s weitere Personen haben sich Ihrem Lob angeschlossen',
    (2, 'u2',    'l'): u'%s Personen und Sie haben dieses Lob ausgesprochen',
    (2, 'me2',   'l'): u'%s Personen haben dieses Lob ausgesprochen'
}

@register.filter
def fb_count(type, count):
    return (type, count)

@register.filter
def fb_me2(pair, me2):
    type = pair[0]
    count = pair[1]
    if count < 2:
        s = others_de.get((count, me2, type), u'Tja .. (%s, %s, %s)' % (count, me2, type))
        return s
    else:
        s = others_de.get((2, me2, type), u'Tsk, tsk .. (%s, %s, %s)' % (count, me2, type))
        if me2 == 'me2':
            count += 1
            # Add one to count, because user and other users voted for it, so add one for the initial user
        return s % count


# truncate string after max characters

@register.filter
def truncate(s, max):
    n = len(s)
    if n > max:
        dots = u' ..'
        return s[0:max-len(dots)] + dots
    else:
        return s


# translate Python booleans to JavaScript

@register.filter
def booljs(x):
    return x and 'true' or 'false'


# decode feedback origin strings

@register.filter
@stringfilter
def fb_origin(origin):
    import re, urllib
    return urllib.unquote(re.sub(r'-([0-9A-F]{2})', lambda mo: '%' + mo.group(0)[1:3], origin).replace('--', '-'))



