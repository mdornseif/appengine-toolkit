#!/usr/bin/env python
# encoding: utf-8
"""
gaetk.tools - various small helpers

Created by Maximillian Dornseif on 2010-11-07.
Copyright (c) 2010 HUDORA. All rights reserved.
"""

import config
config.imported = True

import re


def import_credentials_class():
    """ dynamically import the credentials class bases on the class configured 
        in the settings (config.py). That way there are no project specific configuration
        in the toolkit """
    try:
        config.GAETK_CREDENTIALS_CLASS
    except AttributeError:
        raise Exception('no credentials class configured for the Google AppEngine toolkit!')

    parts = config.GAETK_CREDENTIALS_CLASS.split('.')
    cred_class = parts[-1]
    cred_module = '.'.join(parts[0:-1])
    mod = __import__(cred_module, globals(), locals(), [cred_class])
    return getattr(mod, cred_class)


def split(s):
    """Split a string at spae characters while respecting quoting.

    Unicode version of shlex.split().
    
    >>> split('''A "B and C" D 'E and F' G " "''')
    ['A', 'B and C', 'D', 'E and F', 'G', '']
    >>> split(u'''A "B and C" D 'E and F' G''')
    [u'A', u'B and C', u'D', u'E and F', u'G']
    """ 

    # based on http://stackoverflow.com/questions/79968
    return [x.strip('\'" ') for x in re.split(r"""( |".*?"|'.*?')""", s) if x.strip()]


if __name__ == "__main__":
    import doctest
    doctest.testmod()
