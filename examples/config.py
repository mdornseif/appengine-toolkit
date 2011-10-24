#!/usr/bin/env python
# encoding: utf-8
"""
config.py - general configuration sample for gaetk

Created by Maximillian Dornseif on 2010-09-28.
Copyright (c) 2010 HUDORA. All rights reserved.
"""

import lib  # this initiates the site_dirs

template_dirs = []
template_dirs.append(os.path.join(os.path.dirname(__file__), 'templates'))
template_dirs.append(os.path.join(os.path.dirname(__file__), 'lib/appengine-toolkit/templates'))
