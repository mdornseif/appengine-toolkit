#!/usr/bin/env python
# encoding: utf-8
"""
defaulthandlers.py - handlers implementing common functionality for gaetk

Created by Maximillian Dornseif on 2011-01-09.
Copyright (c) 2011, 2015 HUDORA. All rights reserved.
"""
import config
import datetime
import json
import os

import google.appengine.api.app_identity
import google.appengine.api.memcache

import gaetk
import gaetk.handler

from google.appengine.ext import db
from google.appengine.ext.db import stats


# you can add to plugins to extend the stat handler
# e.g. plugins['rueckmeldungen'] = Rueckmeldung.all().count()
plugins = {}


class gaetk_Stats(db.Expando):
    """Stores some Statistics about AppEngine"""
    d_count = db.IntegerProperty(indexed=False)
    d_bytes = db.IntegerProperty(indexed=False)
    m_count = db.IntegerProperty(indexed=False)
    m_bytes = db.IntegerProperty(indexed=False)
    m_hits = db.IntegerProperty(indexed=False)
    m_hits_bytes = db.IntegerProperty(indexed=False)
    m_misses = db.IntegerProperty(indexed=False)
    m_oldest_item_age = db.IntegerProperty(indexed=False)
    created_at = db.DateTimeProperty(auto_now_add=True)


class Stats(gaetk.handler.BasicHandler):
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
        """Deliver all Statistics available to gaetk."""
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
        # Example Data:
        #  ret = {'datastore': {'count': 526975L,
        #                       'timestamp': '2012-05-05 11:13:01',
        #                       'bytes': 9349778801L,
        #                       'kinds': {u'Credential': {'count': 11L, 'bytes': 39973L},
        #                                 u'_AE_MR_ShardState': {'count': 8L, 'bytes': 9675L},
        #                                 u'Akte': {'count': 167630L, 'bytes': 1212085803L},
        #                                 u'StrConfig': {'count': 2L, 'bytes': 1096L},
        #                                 u'Dokument': {'count': 179660L, 'bytes': 2134737862L},
        #                                 u'DokumentFile': {'count': 179661L, 'bytes': 6002900376L},
        #                                 u'DateTimeConfig': {'count': 2L, 'bytes': 1266L},
        #                                 u'_AE_MR_MapreduceState': {'count': 1L, 'bytes': 2750L}}},
        #         'memcache': {'hits': 5064L,
        #                      'items': 396L,
        #                      'bytes': 4049589L,
        #                      'oldest_item_age': 5409L,
        #                      'misses': 40L,
        #                      'byte_hits': 2665806L}}
        gaetk_Stats(key_name=datetime.datetime.now().strftime('%Y-%m-%dT%H'),  # no minutes
                    d_count=ret['datastore']['count'],
                    d_bytes=ret['datastore']['bytes'],
                    m_count=ret['memcache']['items'],
                    m_bytes=ret['memcache']['bytes'],
                    m_hits=ret['memcache']['hits'],
                    m_hits_bytes=ret['memcache']['byte_hits'],
                    m_misses=ret['memcache']['misses'],
                    m_oldest_item_age=ret['memcache']['oldest_item_age'],
                    ).put()
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(ret))


class RobotTxtHandler(gaetk.handler.BasicHandler):
    """Handler for robots.txt

    Assumes that only the default version should be crawled. For the default version the contents of
    the file `robots.txt` are sent. For all other versions `Disallow: /` is sent.
    """

    def get(self):
        """Deliver robots.txt based on application version."""

        canonical_hostname = getattr(config, 'CANONICAL_HOSTNAME', None)
        if canonical_hostname is None or self.request.host == canonical_hostname:
            # Serve robots.txt for the canonical hostname
            try:
                # read robots.txt
                response = open('robots.txt').read().strip()
            except IOError:
                # robots.txt file not available - use somewhat simple-minded default
                response = 'User-agent: *\nDisallow: /intern\nDisallow: /admin\n'
        else:
            # disable indexing if the request is handled by a non-default version
            response = ('# use http://%s/\nUser-agent: *\nDisallow: /\n'
                        % google.appengine.api.app_identity.get_default_version_hostname())

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(response)


class VersionHandler(gaetk.handler.BasicHandler):
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


class WarmupHandler(gaetk.handler.BasicHandler):
    """Instanz initialisieren"""

    def authchecker(self, method, *args, **kwargs):
        """Authentifizierung abschalten."""
        pass

    def get(self):
        # _strptime importieren. hilft gegen
        # http://groups.google.com/group/google-appengine-python/browse_thread/thread/efbcffa181c32f33
        datetime.datetime.strptime('2000-01-01', '%Y-%m-%d').date()
        self.return_text('ok')


application = gaetk.webapp2.WSGIApplication([
    (r'^/gaetk/stats.json', Stats),
    (r'^/robots.txt', RobotTxtHandler),
    (r'^/version.txt', VersionHandler),
    (r'^/_ah/warmup$', WarmupHandler),
])
