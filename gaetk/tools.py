#!/usr/bin/env python
# encoding: utf-8
"""
gaetk.tools - various small helpers

Created by Maximillian Dornseif on 2010-11-07.
Copyright (c) 2010, 2015 HUDORA. All rights reserved.
"""
import datetime
import os
import re
import unicodedata

import gaetk.lib._lru_cache
import gaetk.lib.memorised.decorators


def split(stos):
    """Split a string at space characters while respecting quoting.

    Unicode version of shlex.split().

    >>> split('''A "B and C" D 'E and F' G " "''')
    ['A', 'B and C', 'D', 'E and F', 'G', '']
    >>> split(u'''A "B and C" D 'E and F' G''')
    [u'A', u'B and C', u'D', u'E and F', u'G']
    """

    # based on http://stackoverflow.com/questions/79968
    return [x.strip('\'" ') for x in re.split(r"""( |".*?"|'.*?')""", stos) if x.strip()]


def get_cookie_domain():
    "Get the 'biggest' domain we can place cookies in."
    host = os.environ.get('HTTP_HOST', '')
    if host.endswith('appspot.com'):
        # setting cookies for .appspot.com does not work
        domain = '.'.join(host.split('.')[-3:])
    else:
        domain = '.'.join(host.split('.')[-2:])
    return domain

# {{{ http://code.activestate.com/recipes/577257/ (r1)
_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')


def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.

    From Django's "django/template/defaultfilters.py".
    """
    if value is None:
        return ''
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore')
    value = unicode(_slugify_strip_re.sub('', value).strip().lower())
    return _slugify_hyphenate_re.sub('-', value)
# end of http://code.activestate.com/recipes/577257/ }}}


class mem_cache(object):
    """Decorator, in Memcache cached."""
    def __init__(self, maxsize='ignored', typed='ignored', ttl=60*30):  # pylint: disable=unused-argument
        """
        If there are decorator arguments, the function
        to be decorated is not passed to the constructor!
        """
        self.ttl = ttl

    def __call__(self, user_function):
        """
        If there are decorator arguments, __call__() is only called
        once, as part of the decoration process! You can only give
        it a single argument, which is the function object.
        """
        return gaetk.lib.memorised.decorators.memorise(ttl=self.ttl)(user_function,)


class hd_cache(object):
    """Decorator, der sowohl Lokal, als auch in Memcache cached."""
    def __init__(self, maxsize=8, typed='ignored', ttl=60*30):  # pylint: disable=unused-argument
        """
        If there are decorator arguments, the function
        to be decorated is not passed to the constructor!
        """
        self.ttl = ttl
        self.maxsize = maxsize

    def __call__(self, user_function):
        """
        If there are decorator arguments, __call__() is only called
        once, as part of the decoration process! You can only give
        it a single argument, which is the function object.
        """
        wraped = gaetk.lib.memorised.decorators.memorise(ttl=self.ttl)(user_function)
        return gaetk.lib._lru_cache.lru_cache(maxsize=self.maxsize, typed=True, ttl=self.ttl)(wraped)


def get_expiration_timestamp(seconds):
    """Generate a HTTP Timestamp."""
    delta = datetime.timedelta(seconds=seconds)
    expiration = datetime.datetime.now() + delta
    return expiration.strftime("%a, %d %b %Y %H:%M:%S %Z")


if __name__ == "__main__":
    import doctest
    doctest.testmod()
