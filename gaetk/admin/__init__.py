#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/admin/__init__.py

Created by Christian Klein on 2011-08-19.
Copyright (c) 2011 HUDORA GmbH. All rights reserved.
"""
import logging
import os
import sys

import config


def import_module(name):
    """Import a module."""

    if name not in sys.modules:
        __import__(name)
    return sys.modules[name]


def autodiscover(appsdir=None):
    """
    Finde alle Admin-Klassen und registriere sie beim globalen Site-Objekt.
    """

    if appsdir is None:
        appsdir = getattr(config, 'ADMIN_APPS_DIR', ['modules'])

    basedir = os.path.dirname(config.__file__)
    for directory in appsdir:
        root = os.path.join(basedir, directory)
        for subdir in os.listdir(root):
            # Ignoriere alle Unterverzeichnisse, in der keine Datei 'admin.py' liegt.
            # Dabei spielt es keine Rolle, ob subdir wirklich ein Verzeichnis ist oder ob
            # es nur eine Datei ist.
            if not os.path.exists(os.path.join(root, subdir, 'admin.py')):
                continue

            module_name = '.'.join((directory, subdir, 'admin'))
            try:
                import_module(module_name)
            except ImportError, error:
                logging.error(u'Error while importing %s: %s', module_name, error)
