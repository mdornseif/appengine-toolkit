#!/usr/bin/env python
# encoding: utf-8
"""
config.py - general configuration sample for gaetk

Created by Maximillian Dornseif on 2010-09-28.
Placed in the Public Domain.
"""

import lib
import os
import sys
lib.imported = True

BASEDIR = os.path.dirname(__file__)

template_dirs = [os.path.join(BASEDIR, 'templates'),
                 os.path.join(BASEDIR, 'lib/appengine-toolkit/templates'),
                 os.path.join(BASEDIR, 'lib/CentralServices/templates')]


DEBUG = True
if not os.environ.get('SERVER_NAME', '').startswith('dev-'):
    DEBUG = False

# Domains to allow OpenID auth on
LOGIN_ALLOWED_DOMAINS = ['hudora.de', 'cyberlogi.de']
OAUTH = {"web": {}}


def main():
    """show path for usage in scripts"""
    print ':'.join(sys.path)

if __name__ == '__main__':
    main()
