#!/usr/bin/env python
# encoding: utf-8
"""
config.py - general configuration sample for gaetk

Created by Maximillian Dornseif on 2010-09-28.
Copyright (c) 2010 HUDORA. All rights reserved.
"""

import sys
import os

newpath = []
_basedir = os.path.dirname(__file__)
libdir = os.path.join(_basedir, 'pythonenv/lib/python2.5/site-packages/')
if os.path.isdir(libdir):
    newpath.append(libdir)
    # appengine doesn't support '.egg-link' links created by pip
    newpath.extend([os.path.join(_basedir,
                        'pythonenv',
                        open(os.path.join(libdir, n)).read().strip('\n.').split('pythonenv')[1])
                for n in os.listdir(libdir) if n.endswith('.egg-link')])

# add all subdirs in ./lib
submoduledir = os.path.join(_basedir, 'lib')
newpath.extend([os.path.join(submoduledir, n)
            for n in os.listdir(submoduledir)
            if os.path.isdir(os.path.join(submoduledir, n))])

sys.path = newpath + sys.path

#from google.appengine.dist import use_library
#use_library('django', '1.1')
#import django

template_dirs = []
template_dirs.append(os.path.join(os.path.dirname(__file__), 'templates'))

def main():
    """show path for usage in scripts"""
    print ':'.join(newpath)

if __name__ == '__main__':
    main()
