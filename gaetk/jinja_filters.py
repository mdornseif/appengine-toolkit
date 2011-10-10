#!/usr/bin/env python
# encoding: utf-8
"""
jinja_filters.py - custom jinja2 filters
Copyright (c) 2010 HUDORA. All rights reserved.
"""


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
    if not value and value != 0:
        return ''
    rev_value = ("%d" % int(value))[::-1]
    value = spacer.join(reversed([rev_value[i:i + 3][::-1] for i in range(0, len(rev_value), 3)]))
    return '<span class="nicenum">%s</span>' % value


def eurocent(value, spacer='&#8239;', decimalplaces=2):
    """Format the given cents as Euro with spacer as delimiter, e.g. '1 234 456.23'

    Obviously works also with US$ and other currnecies.
    Wraps the result in `<span class="currency">`

    use `decimalplaces=0` to cut of cents

    default spacer is NARROW NO-BREAK SPACE U+202F
    probably `style="white-space:nowrap; word-spacing:0.5em;"` would be an CSS based alternative.
    """
    if not value and value != 0:
        return ''
    formatstr = u"%%.%df" % decimalplaces
    rev_value = (formatstr % (int(value) / 100.0))[::-1]
    value = spacer.join(reversed([rev_value[i:i + 3][::-1] for i in range(0, len(rev_value), 3)]))
    return '<span class="currency">%s</span>' % value


def register_custom_filters(jinjaenv):
    """Register the filters to the given Jinja environment."""
    jinjaenv.filters['ljustify'] = left_justify
    jinjaenv.filters['rjustify'] = right_justify
    jinjaenv.filters['nicenum'] = nicenum
    jinjaenv.filters['eurocent'] = eurocent
