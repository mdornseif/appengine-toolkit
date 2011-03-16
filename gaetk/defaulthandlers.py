#!/usr/bin/env python
# encoding: utf-8
"""
defaulthandlers.py - handlers implementing common functionality for gaetk

Created by Maximillian Dornseif on 2011-01-09.
Copyright (c) 2011 HUDORA. All rights reserved.
"""


from django.utils import simplejson
from google.appengine.ext import webapp
from google.appengine.ext.db import stats
from google.appengine.ext.webapp.util import run_wsgi_app
import google.appengine.api.memcache

# you can add to plugins to extend the stat handler
# e.g. plugins['rueckmeldungen'] = Rueckmeldung.all().count()
plugins = {}


class Stats(webapp.RequestHandler):
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


def main():
    application = webapp.WSGIApplication([
                      ('/gaetk/stats.json', Stats),
                      ],
                     )
    run_wsgi_app(application)


if __name__ == '__main__':
    main()
