#!/usr/bin/env python
# encoding: utf-8
"""
jinja_filters.py - custom jinja2 filters
Copyright (c) 2010, 2012, 2014 HUDORA. All rights reserved.
"""

import json
import re

import jinja2
from jinja2.utils import Markup


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


def plural(value, singular_str, plural_str):
    """Return value with singular or plural form"""
    if not isinstance(value, (int, long)):
        return singular_str

    if value == 1:
        return singular_str
    return plural_str


def filter_dateformat(value, formatstring='%Y-%m-%d'):
    """Formates a date"""

    from huTools.calendar.formats import convert_to_date
    from babel import dates
    date = convert_to_date(value)
    # We do not want locale specific formating, clamp on ISO 8601
    # TODO: why use babel then?
    return dates.format_date(date, formatstring, locale='de_DE')


def filter_markdown(value):
    """
    Rendert a string as Markdown

    Syntax:
        {{ value|markdown }}
    """

    import huTools.markdown2
    return Markup(huTools.markdown2.markdown(value))


@jinja2.evalcontextfilter
def filter_nl2br(eval_ctx, value):
    """Newlines in <br>-Tags konvertieren"""
    paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')
    result = u'\n\n'.join(u'<p>%s</p>' % paragraph.replace('\n', '<br>\n')
                          for paragraph in paragraph_re.split(value))
    if eval_ctx.autoescape:
        result = Markup(result)
    return result


def filter_urlquote(value):
    """Makes a string valid in an URL."""
    import huTools.http.tools

    if type(value) == 'Markup':
        value = value.unescape()
    return huTools.http.tools.quote(value)


def register_custom_filters(jinjaenv):
    """Register the filters to the given Jinja environment."""
    jinjaenv.filters['ljustify'] = left_justify
    jinjaenv.filters['rjustify'] = right_justify
    jinjaenv.filters['nicenum'] = nicenum
    jinjaenv.filters['eurocent'] = eurocent
    jinjaenv.filters['to_json'] = to_json
    jinjaenv.filters['plural'] = plural
    jinjaenv.filters['filter_dateformat'] = plural
    jinjaenv.filters['filter_markdown'] = plural
    jinjaenv.filters['filter_nl2br'] = plural
