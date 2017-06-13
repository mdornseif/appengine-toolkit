#!/usr/bin/env python
# encoding: utf-8
"""
jinja_filters.py - custom jinja2 filters
Copyright (c) 2010, 2012, 2014, 2017 HUDORA. All rights reserved.
"""
import decimal
import json
import logging
import re

import jinja2

from jinja2.utils import Markup

import gaetk.tools


def left_justify(value, width):
    """Prefix the given string with spaces until it is width characters long."""
    return unicode(value or '').ljust(int(width))


def right_justify(value, width):
    """Postfix the given string with spaces until it is width characters long."""
    stripped = unicode(value or '')[0:width]
    return stripped.rjust(int(width))


def to_json(value):
    """Convert the given Value to JSON.

    Very helpful to use in Javascript."""
    return json.dumps(value)


def _make_attrgetter(environment, attribute):
    """Returns a callable that looks up the given attribute from a
    passed object with the rules of the environment. Dots are allowed
    to access attributes of attributes.
    """
    if not isinstance(attribute, basestring) or '.' not in attribute:
        return lambda x: environment.getitem(x, attribute)
    attribute = attribute.split('.')

    def attrgetter(item):
        """Closure."""
        for part in attribute:
            item = environment.getitem(item, part)
        return item
    return attrgetter


def plural(value, singular_str, plural_str):
    """Return value with singular or plural form"""
    if not isinstance(value, (int, long)):
        return singular_str

    if value == 1:
        return singular_str
    return plural_str


def none(value):
    """converts `None` to ''"""
    if value is None:
        return u''
    return value


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
        return Markup(result)
    return result


@jinja2.contextfilter
def filter_authorize(context, value, permission_types):
    """Display content only if the current logged in user has a specific permission"""

    if not isinstance(permission_types, list):
        permission_types = [permission_types]

    granted = not context.get('request').get('_gaetk_disable_permissions', False)
    for permission in permission_types:
        if context.get('credential') and permission in context.get('credential').permissions:
            granted = True
            break

    if granted:
        value = '<span class="restricted">%s</span>' % (value)
    else:
        value = u'…<!-- Berechtigung %s -->' % (', '.join(permission_types))
        if not context.get('credential'):
            logging.info('context has no credential!')

    if context.eval_ctx.autoescape:
        return Markup(value)
    return value


def filter_tertial(value):
    """Wandelt ein Date oder Datetime-Objekt in einen Tertial-String."""
    from huTools.calendar.formats import tertial
    if not value:
        return ''
    return tertial(value)


def filter_to_date(value):
    """Wandelt ein Date oder Datetime-Objekt in einen Date-Objekt."""
    from huTools.calendar.formats import convert_to_date
    if not value:
        return ''
    return convert_to_date(value)


def filter_dateformat(value, formatstring='%Y-%m-%d'):
    """Formates a date."""
    from huTools.calendar.formats import convert_to_date
    if not value:
        return ''
    return Markup(convert_to_date(value).strftime(formatstring).replace('-', '&#8209;'))


def filter_datetime(value, formatstring='%Y-%m-%d %H:%M'):
    """Formates a datetime."""
    from huTools.calendar.formats import convert_to_datetime
    if not value:
        return ''
    return Markup(convert_to_datetime(value).strftime(formatstring).replace('-', '&#8209;'))


def filter_yesno(value, answers='yes,no,maybe'):
    """Beispiel: {{ value|yesno:"yeah,nope,maybe" }}."""

    bits = answers.split(u',')
    if len(bits) == 3:
        vyes, vno, vmaybe = bits
    elif len(bits) == 2:
        vyes, vno, vmaybe = bits[0], bits[1], bits[1]
    else:
        return value

    if value is None:
        return vmaybe
    if value:
        return vyes
    return vno


def filter_onoff(value):
    """Boolean als Icon darstellen."""
    if value:
        return Markup('<i class="fa fa-toggle-on" aria-hidden="true" style="color:green"></i>')
    else:
        return Markup('<i class="fa fa-toggle-off" aria-hidden="true" style="color:red"></i>')


def percent(value):
    """Fomat Percent and handle None"""
    if value is None:
        return u'␀'
    return "%.0f" % float(value)


def nicenum(value, spacer='&#8239;', plain=False):
    """Format the given number with spacer as delimiter, e.g. '1 234 456.23'

    Wraps the result in `<span class="nicenum">`

    default spacer is NARROW NO-BREAK SPACE U+202F
    probably `style="white-space:nowrap; word-spacing:0.5em;"` would be an CSS based alternative.
    """
    if value is None:
        return u'␀'
    rev_value = ("%d" % int(value))[::-1]
    value = spacer.join(reversed([rev_value[i:i + 3][::-1] for i in range(0, len(rev_value), 3)]))
    if plain:
        return value
    else:
        return '<span class="nicenum">%s</span>' % value


def eurocent(value, spacer='&#8239;', decimalplaces=2, plain=False):
    """Format the given cents as Euro with spacer as delimiter, e.g. '1 234 456.23'

    Obviously works also with US$ and other currencies.
    Wraps the result in `<span class="currency">`

    use `decimalplaces=0` to cut of cents

    default spacer is NARROW NO-BREAK SPACE U+202F
    probably `style="white-space:nowrap; word-spacing:0.5em;"` would be an CSS based alternative.
    """
    if value is None:
        return u'␀'
    tmp = str(int(value) / decimal.Decimal(100))
    # Cent anhängen
    if '.' not in tmp:
        tmp += '.'
    euro_value, cent_value = tmp.split('.')
    cent_value = cent_value.ljust(decimalplaces, '0')[:decimalplaces]
    rev_value = euro_value[::-1]
    euro_value = spacer.join(reversed([rev_value[i:i + 3][::-1] for i in range(0, len(rev_value), 3)]))
    if plain:
        return '%s.%s' % (euro_value, cent_value)
    else:
        return '<span class="currency">%s.%s</span>' % (euro_value, cent_value)


def euroword(value, plain=False):
    """Fomat Cents as pretty Euros"""
    if value is None:
        return u'␀'
    return _formatint(value / 100)

# Aus Django


@jinja2.contextfilter
def intword(_context, value):
    """
    Converts a large integer to a friendly text representation. Works best for
    numbers over 1 million. For example, 1000000 becomes '1.0 Mio', 1200000
    becomes '1.2 Mio' and '1200000000' becomes '1200 Mio'.
    """
    return _formatint(value)


def _formatint(value):
    """Format an Integer nicely with spacing"""
    if value is None:
        return u'␀'
    value = int(value)
    if abs(value) < 1000000:
        rev_value = ("%d" % int(value))[::-1]
        return u' '.join(reversed([rev_value[i:i + 3][::-1] for i in range(0, len(rev_value), 3)]))
    else:
        new_value = value / 1000000.0
        return '%(value).1f Mio' % {'value': new_value}
    return value


def filter_attrencode(value):
    """Makes a string valid as an XML attribute."""
    import xml.sax.saxutils
    if value is None:
        return u''
    if hasattr(value, 'unescape'):  # jinja2 Markup
        value = value.unescape()
    return xml.sax.saxutils.quoteattr(value)[1:-1]


def filter_cssencode(value):
    """Makes a string valid as an CSS class name."""
    if value is None:
        return u''
    ret = re.sub('[^A-Za-z0-9-_]+', '-', value)
    if ret.startswith(tuple('-0123456789')):
        ret = 'CSS' + ret
    return ret


def filter_urlencode(value):
    """Encode string for usage in URLs"""
    import urllib
    if isinstance(value, Markup):
        value = value.unescape()
    value = value.encode('utf8')
    value = urllib.quote(value)
    return Markup(value)


def register_custom_filters(jinjaenv):
    """Register the filters to the given Jinja environment."""
    jinjaenv.filters['ljustify'] = left_justify
    jinjaenv.filters['rjustify'] = right_justify
    jinjaenv.filters['to_json'] = to_json
    jinjaenv.filters['plural'] = plural
    jinjaenv.filters['none'] = none
    jinjaenv.filters['markdown'] = filter_markdown
    jinjaenv.filters['nl2br'] = filter_nl2br
    jinjaenv.filters['authorize'] = filter_authorize
    jinjaenv.filters['tertial'] = filter_tertial
    jinjaenv.filters['to_date'] = filter_to_date
    jinjaenv.filters['dateformat'] = filter_dateformat
    jinjaenv.filters['datetime'] = filter_datetime
    jinjaenv.filters['yesno'] = filter_yesno
    jinjaenv.filters['onoff'] = filter_onoff
    jinjaenv.filters['percent'] = percent
    jinjaenv.filters['nicenum'] = nicenum
    jinjaenv.filters['eurocent'] = eurocent
    jinjaenv.filters['euroword'] = euroword
    jinjaenv.filters['intword'] = intword
    jinjaenv.filters['attrencode'] = filter_attrencode
    jinjaenv.filters['cssencode'] = filter_cssencode
    jinjaenv.filters['urlencode'] = filter_urlencode
    jinjaenv.filters['slugify'] = gaetk.tools.slugify
