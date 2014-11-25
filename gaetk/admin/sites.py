#!/usr/bin/env python
# encoding: utf-8
"""
common/admin/sites.py

Created by Christian Klein on 2011-08-19.
Copyright (c) 2011 HUDORA GmbH. All rights reserved.
"""
import config
config.imported = True

from gaetk.admin.options import ModelAdmin


class AdminSite(object):
    """Konzept zur Verwaltung (per Weboberfläche) adminsitrierbarer GAE Models."""

    def __init__(self):
        """Konstruktor."""
        self._registry = {}

    def register(self, model_class, admin_class=None):
        """Registers the given model with the given admin class."""

        if not admin_class:
            admin_class = ModelAdmin

        # # Don't import the humongous validation code unless required
        # if admin_class and settings.DEBUG:
        #     from django.contrib.admin.validation import validate
        # else:
        #     validate = lambda model, adminclass: None

        if model_class in self._registry:
            pass
            # raise RuntimeError('The model %s is already registered' % model_class.kind())

        # Instantiate the admin class to save in the registry
        self._registry[model_class] = admin_class(model_class, self)

    def registry(self):
        """Gib eine Kopie der Registry zurück"""
        return dict(self._registry)


# The global AdminSite instance
site = AdminSite()
