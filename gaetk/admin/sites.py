#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/admin/sites.py

Created by Christian Klein on 2011-08-19.
Copyright (c) 2011 HUDORA GmbH. All rights reserved.
"""
import logging

from gaetk.admin import util
from gaetk.compat import xdb_kind


class AdminSite(object):
    """Konzept zur Verwaltung (per Weboberfläche) adminsitrierbarer GAE Models."""

    def __init__(self):
        """Konstruktor."""
        self._registry = {}

    def get_admin_class(self, key):
        return self._registry.get(key)

    def register(self, model_class, admin_class=None):
        """Registers the given model with the given admin class."""

        if admin_class is None:
            from gaetk.admin.options import ModelAdmin
            admin_class = ModelAdmin

        # # Don't import the humongous validation code unless required
        # if admin_class and settings.DEBUG:
        #     from django.contrib.admin.validation import validate
        # else:
        #     validate = lambda model, adminclass: None

        if model_class in self._registry:
            logging.warn(u'The model %s is already registered', xdb_kind(model_class))

        # Instantiate the admin class to save in the registry
        self._registry[model_class] = admin_class(model_class, self)

    @property
    def registry(self):
        """Gib eine Kopie der Registry zurück"""
        return dict(self._registry)

    def get_model_class(self, application, model):
        """Klasse zu 'model' zurückgeben."""

        for model_class in self._registry:
            if model == xdb_kind(model_class) and application == util.get_app_name(model_class):
                return model_class


# The global AdminSite instance
site = AdminSite()
