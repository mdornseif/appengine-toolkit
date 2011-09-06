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


def eurocent(value, spacer=''):
    """Format the given cents as Euro with spacer as delimiter, e.g. '1 234 456'"""
    if not value:
        return ''
    rev_value = (u"%.0f" % (int(value) / 100.0))[::-1]
    return spacer.join(reversed([rev_value[i:i + 3][::-1] for i in range(0, len(rev_value), 3)]))


def register_custom_filters(jinjaenv):
    """Register the filters to the given Jinja environment."""
    jinjaenv.filters['ljustify'] = left_justify
    jinjaenv.filters['rjustify'] = right_justify
    jinjaenv.filters['eurocent'] = eurocent
