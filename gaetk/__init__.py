#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/__init__.py

Created by Maximillian Dornseif on 2010-10-31.
Copyright (c) 2010, 2012, 2015 HUDORA. All rights reserved.
"""

try:
    import webapp2  # on AppEngine python27
except ImportError:
    pass

from gaetk import handler
from gaetk.lib import _gaesessions as gaesessions


__all__ = [
    'webapp2', 'configuration', 'compat', 'handler', 'infrastructure', 'tools',
    'gaesessions']
