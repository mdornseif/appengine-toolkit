#!/usr/bin/env python
# encoding: utf-8
"""
handler.py - default Request Handler

Created by Maximillian Dornseif on 2010-10-03.
Copyright (c) 2010 HUDORA. All rights reserved.
"""

# pylint can't handle db.Model.get()
# pylint: disable=E1103
# pylint can't handle google.appengine.api.memcache
# pylint: disable=E1101

import config
config.imported = True

from google.appengine.ext import webapp
#from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import logging
import urlparse


class BasicHandler(webapp.RequestHandler):
    """Generische Handler Funktionalität."""
    def abs_url(self, url):
        return urlparse.urljoin(self.request.uri, url)

    def error(self, code):
        """Clears the response output stream and sets the given HTTP error code.

        Args:
          code: the HTTP status error code (e.g., 501)
        """
        logging.info('Errorhandler')
        super(BasicHandler, self).error(code)
        if str(code) == '404':
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write('Daten nicht gefunden.')

    #def render(self, values, template_name):
    #    """Render a Jinja2 Template"""
    #    env = Environment(loader=FileSystemLoader(config.template_dirs))
    #    try:
    #        template = env.get_template(template_name)
    #    except TemplateNotFound:
    #        raise TemplateNotFound(template_name)
    #    myval = dict(credential=self.credential, uri=self.request.url, navsection=None)
    #    myval.update(values)
    #    content = template.render(myval)
    #    self.response.out.write(content)

    def paginate(self, query, defaultcount=10, datanodename='objects', calctotal=True, formatter=None):
        """Pagination a la  http://mdornseif.github.com/2010/10/02/appengine-paginierung.html

        Returns something like
        {more_objects=True, prev_objects=True,
         prev_start=10, next_start=30,
         objects: [...], cursor='ABCDQWERY'}
        """
        start = self.request.get_range('start', min_value=0, max_value=1000, default=0)
        limit = self.request.get_range('limit', min_value=1, max_value=100, default=defaultcount)
        if self.request.get('cursor'):
            query.with_cursor(self.request.get('cursor'))
        objects = query.fetch(limit + 1, start)
        more_objects = len(objects) > limit
        objects = objects[:limit]
        prev_objects = start > 0
        prev_start = max(start - limit - 1, 0)
        next_start = max(start + len(objects) - 1, 0)
        ret = dict(more_objects=more_objects, prev_objects=prev_objects,
                   prev_start=prev_start, next_start=next_start)
        if more_objects:
            ret['cursor'] = query.cursor()
        if calctotal:
            ret['total'] = query.count()
        if formatter:
            ret[datanodename] = objects
        else:
            ret[datanodename] = [formatter(x) for x in objects]
        return ret
