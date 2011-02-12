#!/usr/bin/env python
# encoding: utf-8
"""
gaetk.tools - various small helpers

Created by Maximillian Dornseif on 2010-11-07.
Copyright (c) 2010 HUDORA. All rights reserved.
"""

import re


def split(s):
    """Split a string at space characters while respecting quoting.

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
