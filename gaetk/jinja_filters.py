#!/usr/bin/env python
# encoding: utf-8
"""
jinja_filters.py - custom jinja2 filters
Copyright (c) 2010, 2012 HUDORA. All rights reserved.
"""

import json
from itertools import groupby
from operator import itemgetter


def left_justify(value, width):
    """Prefix the given string with spaces until it is width characters long."""
    return unicode(value or '').ljust(int(width))


def right_justify(value, width):
    """Postfix the given string with spaces until it is width characters long."""
    stripped = unicode(value or '')[0:width]
    return stripped.rjust(int(width))


def nicenum(value, spacer='&#8239;'):
    """Format the given number with spacer as delimiter, e.g. '1 234 456.23'

    Wraps the result in `<span class="nicenum">`

    default spacer is NARROW NO-BREAK SPACE U+202F
    probably `style="white-space:nowrap; word-spacing:0.5em;"` would be an CSS based alternative.
    """
    if value != 0 and not value:
        return ''
    rev_value = ("%d" % int(value))[::-1]
    value = spacer.join(reversed([rev_value[i:i + 3][::-1] for i in range(0, len(rev_value), 3)]))
    return '<span class="nicenum">%s</span>' % value


def eurocent(value, spacer='&#8239;', decimalplaces=2, plain=False):
    """Format the given cents as Euro with spacer as delimiter, e.g. '1 234 456.23'

    Obviously works also with US$ and other currencies.
    Wraps the result in `<span class="currency">`

    use `decimalplaces=0` to cut of cents

    default spacer is NARROW NO-BREAK SPACE U+202F
    probably `style="white-space:nowrap; word-spacing:0.5em;"` would be an CSS based alternative.
    """
    if not value and value != 0:
        return ''
    tmp = u"%.*f" % (decimalplaces, (int(value) / 100.0))
    euro_value, cent_value = tmp.split('.')
    rev_value = euro_value[::-1]
    euro_value = spacer.join(reversed([rev_value[i:i + 3][::-1] for i in range(0, len(rev_value), 3)]))
    if plain:
        return '%s.%s' % (euro_value, cent_value)
    else:
        return '<span class="currency">%s.%s</span>' % (euro_value, cent_value)


def to_json(value):
    """Convert the given Value to JSON.

    Very helpful to use in Javascript."""
    return json.dumps(value)


<<<<<<< HEAD

def make_attrgetter(environment, attribute):
    """Returns a callable that looks up the given attribute from a
    passed object with the rules of the environment.  Dots are allowed
    to access attributes of attributes.
    """
    if not isinstance(attribute, basestring) or '.' not in attribute:
        return lambda x: environment.getitem(x, attribute)
    attribute = attribute.split('.')
    def attrgetter(item):
        for part in attribute:
            item = environment.getitem(item, part)
        return item
    return attrgetter


def do_groupbyr(environment, value, attribute):
    """reversed groupby"""
    expr = make_attrgetter(environment, attribute)
    return sorted(map(_GroupTuple, groupby(sorted(value, key=expr, reverse=True), expr)), reverse=True)
do_groupbyr.environmentfilter = True


class _GroupTuple(tuple):
    __slots__ = ()
    grouper = property(itemgetter(0))
    list = property(itemgetter(1))

    def __new__(cls, (key, value)):
        return tuple.__new__(cls, (key, list(value)))

def plural(value, singular_str, plural_str):
    """Return value with singular or plural form"""
    if not isinstance(value, (int, long)):
        return singular_str

    if value == 1:
        return singular_str
    return plural_str


def register_custom_filters(jinjaenv):
    """Register the filters to the given Jinja environment."""
    jinjaenv.filters['ljustify'] = left_justify
    jinjaenv.filters['rjustify'] = right_justify
    jinjaenv.filters['nicenum'] = nicenum
    jinjaenv.filters['eurocent'] = eurocent
    jinjaenv.filters['to_json'] = to_json
    jinjaenv.filters['groupbyr'] = do_groupbyr
    jinjaenv.filters['plural'] = plural
