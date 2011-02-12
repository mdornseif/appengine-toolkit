#!/usr/bin/env python
# encoding: utf-8
"""
defaulthandlers.py - handlers implementing common functionality for gaetk

Created by Maximillian Dornseif on 2011-01-09.
Copyright (c) 2011 HUDORA. All rights reserved.
"""

from django.utils import simplejson
from google.appengine.ext.db import stats
import gaetk.handler
import google.appengine.api.memcache
import gaetk.webapp2
import logging


class Stats(gaetk.handler.BasicHandler):
    def get(self):
        ret = dict(memcache=google.appengine.api.memcache.get_stats())
        global_stat = stats.GlobalStat.all().get()
        if global_stat:
            ret.update(dict(datastore=dict(bytes=global_stat.bytes,
                                           count=global_stat.count)))
            timestamp = global_stat.timestamp
            kind_stat = stats.KindStat.all().filter("timestamp =", timestamp).fetch(1000)
            logging.info([stat.kind_name for stat in kind_stat])
            kind_list = [stat.kind_name for stat in kind_stat
                         if stat.kind_name and not stat.kind_name.startswith('__')]
            kind_set = set(kind_list)
            ret['datastore']['kinds'] = len(kind_list)
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(simplejson.dumps(ret))


def main():
    application = gaetk.webapp2.WSGIApplication([
                      ('/gaetk/stats.json', Stats),
                      ],
                     )
    application.run()


if __name__ == '__main__':
    main()

