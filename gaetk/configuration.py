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
Copyright (c) 2011, 2012 HUDORA. All rights reserved.
"""
import json

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
