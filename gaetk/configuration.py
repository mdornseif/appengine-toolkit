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

Values are locally cached for 10 seconds, but the cache can be flushed
with the provided FlushConfigCacheHandler.
The handler needs to be included in handlers section of app.yaml:

For Python 2.5 Runtime:
handlers:
- url: /config/.*
  script: lib/gaetk/gaetk/configuration.py

Created by Christian Klein on 2011-11-24.
Copyright (c) 2011, 2012 HUDORA. All rights reserved.
"""

import config
config.imported = True

import json
import time

import gaetk
import gaetk.handler
from google.appengine.ext import db

CONFIG_CACHE = {}


class Configuration(db.Model):
    """Generic configuration object"""
    value = db.StringProperty(default=u'')


def get_config(key, default=None):
    """Get (cached) configuration value for key"""

    if key in CONFIG_CACHE:
        if CONFIG_CACHE.get(key[0]) > time.time() + 10:
            return CONFIG_CACHE.get(key)[1]

    obj = Configuration.get_by_key_name(key)
    if obj:
        CONFIG_CACHE[key] = (time.time(), json.loads(obj.value))
        return CONFIG_CACHE.get(key)[1]
    else:
        return set_config(key, default)


def set_config(key, value):
    """Set configuration value for key"""

    obj = Configuration.get_or_insert(key_name=key)
    obj.value = json.dumps(value)
    CONFIG_CACHE[key] = (time.time(), value)
    obj.put()
    return value


class FlushConfigCacheHandler(gaetk.handler.BasicHandler):
    """Handler for flushing the cached config objects"""

    def get(self):
        """Does not expect any parameters"""
        CONFIG_CACHE.clear()
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('ok\n')


application = gaetk.webapp2.WSGIApplication([('.*/flush', FlushConfigCacheHandler)])


def main():
    """Main Entry Point for Python 2.5 Runtime"""
    application.run()


if __name__ == "__main__":
    main()
