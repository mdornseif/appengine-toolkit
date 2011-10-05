#!/usr/bin/env python
# encoding: utf-8
"""
defaulthandlers.py - handlers implementing common functionality for gaetk

Created by Maximillian Dornseif on 2011-01-09.
Copyright (c) 2011 HUDORA. All rights reserved.
"""

import datetime
import os

import appengine.api.app_identity
import google.appengine.api.memcache

import gaetk.handler
import gaetk.webapp2
from django.utils import simplejson
from google.appengine.ext.db import stats


# you can add to plugins to extend the stat handler
# e.g. plugins['rueckmeldungen'] = Rueckmeldung.all().count()
plugins = {}


class Stats(gaetk.handler.BaseHandler):
    """Generic Statistics Handler."""
    # Example:
    # {"datastore": {"count": 380850,
    #                "kinds": 10,
    #                "bytes": 436516810},
    #  "memcache": {"hits": 320489,
    #               "items": 44,
    #               "bytes": 43166,
    #               "oldest_item_age": 3175,
    #               "misses": 20606,
    #               "byte_hits": 176865465}
    # }
    def get(self):

        # memcache statistics are straightforward
        ret = dict(memcache=google.appengine.api.memcache.get_stats())

        # Getting datastore statistics is slightly more involved. We have to extract a
        # timestamp from `stats.GlobalStat.all().get()` and use that to access `stats.KindStat`:
        global_stat = stats.GlobalStat.all().get()
        if global_stat:
            timestamp = global_stat.timestamp
            ret.update(dict(datastore=dict(bytes=global_stat.bytes,
                                           count=global_stat.count,
                                           timestamp=str(timestamp))))

            ret['datastore']['kinds'] = {}
            for kindstat in stats.KindStat.all().filter("timestamp =", timestamp).fetch(200):
                if kindstat.kind_name and not kindstat.kind_name.startswith('__'):
                    ret['datastore']['kinds'][kindstat.kind_name] = dict(bytes=kindstat.bytes,
                                                                     count=kindstat.count)

        for name, func in plugins.items():
            ret[name] = func()

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(simplejson.dumps(ret))


class RobotTxtHandler(gaetk.handler.BaseHandler):
    """Handler for robots.txt

    Assumes that only the default version should be crawled. For the default version the contents of
    the file `robots.txt` are sent. For all other versions `Disallow: /` is sent.
    """

    def get(self):
        """Deliver robots.txt based on application version."""

        if self.request.host.startswith(appengine.api.app_identity.get_default_version_hostname()):
            # we are running the default Version
            try:
                # read robots.txt
                response = open('robots.txt').read().strip()
            except IOError:
                # robots.txt file not available - use somewhat simple-minded default
                response = 'User-agent: *\nDisallow: /intern\nDisallow: /admin\n'
        else:
            # we are not running the default version - disable indexing
            response = ('# use http://%s/\nUser-agent: *\nDisallow: /\n'
                        % appengine.api.app_identity.get_default_version_hostname())

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(response)


class VersionHandler(gaetk.handler.BaseHandler):
    """Version Handler - allows clients to see the git revision currently running."""

    def get(self):
        """Returns the first line of version.txt.

        When deploying we do something like `git show-ref --hash=7 HEAD > version.txt` just before
        `appcfg.py update`. This view allows to retrive the data."""

        try:
            version = open("version.txt").readline().strip()
            stat = os.stat("version.txt")
            last_modified = datetime.datetime.fromtimestamp(stat.st_ctime)
            self.response.headers['Last-Modified'] = last_modified.strftime('%a, %d %b %y %H:%M:%S GMT')
        except IOError:
            # if there is no version.txt file we return `unkonown`.
            version = 'unknown'

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(version + '\n')


def main():
    app = gaetk.webapp2.WSGIApplication([
                                         ('/gaetk/stats.json', Stats),
                                         ('/robots.txt', RobotTxtHandler),
                                         ('/version.txt', VersionHandler),
                                         ])
    app.run()


if __name__ == '__main__':
    main()
