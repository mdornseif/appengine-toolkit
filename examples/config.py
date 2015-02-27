#!/usr/bin/env python
# encoding: utf-8
"""
config.py - general configuration for www.hudora.de 

Created by Maximillian Dornseif on 2015-02-28.
Copyright (c) 2015 HUDORA. All rights reserved.
"""

import os
import sys
import lib
lib.imported = True

template_dirs = []
template_dirs.append(os.path.join(os.path.dirname(__file__), './templates'))
template_dirs.append(os.path.join(os.path.dirname(__file__), './lib/appengine-toolkit/templates'))
template_dirs.append(os.path.join(os.path.dirname(__file__), './lib/CentralServices/templates'))

# Domains to allow OpenID auth on
LOGIN_ALLOWED_DOMAINS = ['hudora.de']
OAUTH = {"web": {
}}

def main():
    """show path for usage in scripts"""
    print ':'.join(sys.path)

if __name__ == '__main__':
    main()
