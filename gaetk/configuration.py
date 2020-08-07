#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/configuration.py

This module provides a generic configuration object.
The two functions get_config and set_config are used
to get or set the configuration object.

>>> from gaetk import configuration
>>> configuration.get_config('MY-KEY-NAME')
None
>>> configuration.get_config('MY-KEY-NAME', default=55555)
55555
>>> configuration.set_config('MY-KEY-NAME', u'5711')
>>> configuration.get_config('MY-KEY-NAME')
u'5711'

Created by Christian Klein on 2011-11-24.
Copyright (c) 2011, 2012, 2016, 2017 HUDORA. All rights reserved.
"""
import json
import logging

import gaetk.handler

from google.appengine.ext import ndb


class gaetk_Configuration(ndb.Model):
    """Generic configuration object"""
    value = ndb.TextProperty(default=u'', indexed=False)
    updated_at = ndb.DateTimeProperty(auto_now_add=True, auto_now=True)
    created_at = ndb.DateTimeProperty(auto_now_add=True)


def get_config(key, default=None):
    """Get configuration value for key"""

    obj = gaetk_Configuration.get_by_id(key)
    if obj:
        return json.loads(obj.value)
    return set_config(key, default)


def get_config_multi(keys):
    """Get multiple configuration values, no defaults"""

    objs = ndb.get_multi([ndb.Key(gaetk_Configuration, key) for key in keys])
    return dict((obj.key.id(), obj.value) for obj in objs if obj is not None)


def set_config(key, value):
    """Set configuration value for key"""

    obj = gaetk_Configuration(id=key, value=json.dumps(value))
    obj.put()
    return value


class ConfigHandler(gaetk.handler.JsonResponseHandler):
    """Handler für Configurationsobjekte"""

    def authchecker(self, *args, **kwargs):
        """Nur Admin-User"""

        self.login_required()
        if not self.is_admin():
            raise gaetk.handler.HTTP403_Forbidden

    def get(self, key):
        """Lese Konfigurationsvariable"""
        obj = gaetk.handler.get_object_or_404(gaetk_Configuration, key)
        self.response.headers['Last-Modified'] = obj.updated_at.strftime('%a, %d %b %Y %H:%M:%S GMT')
        return obj.value

    def post(self, key):
        """Schreibe Konfigurationsvariable"""

        header = self.request.headers.get('Content-Type')
        if header.split(';', 1)[0] == 'application/json':
            data = self.request.body
        else:
            data = self.request.get('value', '')

        try:
            value = json.loads(data)
        except (ValueError, TypeError) as exception:
            logging.exception(u'Err: %r, %s', data, exception)
            raise gaetk.handler.HTTP400_BadRequest
        return set_config(key, value)


application = gaetk.handler.WSGIApplication([
    (r'.*/([\w_-]+)/', ConfigHandler),
])
