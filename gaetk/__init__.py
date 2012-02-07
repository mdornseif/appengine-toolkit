#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/__init__.py

Created by Maximillian Dornseif on 2010-10-31.
Copyright (c) 2010 HUDORA. All rights reserved.
"""

try:
    import webapp2  # on AppEngine python27
except ImportError:
    import mywebapp2 as webapp2  # on AppEngine python25
