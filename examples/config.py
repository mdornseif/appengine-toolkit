#!/usr/bin/env python
# encoding: utf-8
"""
config.py - general configuration sample for gaetk

Created by Maximillian Dornseif on 2010-09-28.
Copyright (c) 2010, 2011 HUDORA. All rights reserved.
"""

import os
import sys

template_dirs = []
template_dirs.append(os.path.join(os.path.dirname(__file__), 'templates'))
template_dirs.append(os.path.join(os.path.dirname(__file__), 'lib/gaetk/templates'))

# Domains to allow OpenID auth on
LOGIN_ALLOWED_DOMAINS = ['hudora.de']

ALLOWED_PERMISSIONS = [
  'einkaufspreise',  # Der Nutzer darf Einkaufspreise und den Materialeinsatz 1 & 4 sehen
  'wertschoepfung',  # Der Benutzer darf die Wertschöpfung für alle Kunden sehen
]


def main():
    """show path for usage in scripts"""
    print ':'.join(sys.path)

if __name__ == '__main__':
    main()
