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
Copyright (c) 2011, 2012, 2016 HUDORA. All rights reserved.
"""
import json

import gaetk.handler

from google.appengine.ext import ndb


class Configuration(ndb.Model):
    """Generic configuration object"""
    value = ndb.JsonProperty(default=u'')
    updated_at = ndb.DateTimeProperty(auto_now_add=True, auto_now=True)


def get_config(key, default=None):
    """Get configuration value for key"""

    obj = Configuration.get_by_id(key)
    if obj:
        return obj.value  # json.loads(obj.value)
    else:
        return set_config(key, default)


def get_config_multi(keys):
    """Get multiple configuration values, no defaults"""

    objs = ndb.get_multi([ndb.Key(Configuration, key) for key in keys])
    return dict((obj.key.id(), obj.value) for obj in objs if obj is not None)


def set_config(key, value):
    """Set configuration value for key"""

    obj = Configuration(id=key, value=value)  # json.dumps(value)).put()
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
        obj = gaetk.handler.get_object_or_404(Configuration, key)
        self.response.headers['Last-Modified'] = obj.updated_at.strftime('%a, %d %b %Y %H:%M:%S GMT')
        return obj.value

    def post(self, key):
        """Schreibe Konfigurationsvariable"""

        import logging
        header = self.request.headers.get('Content-Type')
        if header.split(';', 1)[0] != 'application/json':
            logging.debug(u'%s not json?', self.request.headers.get('Content-Type'))
            raise gaetk.handler.HTTP400_BadRequest
        try:
            value = json.loads(self.request.body)
        except (ValueError, TypeError) as exception:
            logging.error(u'body: %r, exception: %s', self.request.body, exception)
            raise gaetk.handler.HTTP400_BadRequest

        obj = Configuration.get_or_insert(key)
        obj.value = value
        obj.put()
        return obj.value


application = gaetk.handler.WSGIApplication([
    (r'.*/(\w+)/', ConfigHandler),
])
