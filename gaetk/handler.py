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

from gaetk import webapp2
import logging
import urlparse
from gaetk.gaesessions import get_current_session
from google.appengine.api import memcache
from google.appengine.ext import webapp
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import logging
from ablage.models import Credential
import urllib
import urlparse

from webob.exc import HTTPUnauthorized as HTTP401_Unauthorized
from webob.exc import HTTPForbidden as HTTP403_Forbidden
from webob.exc import HTTPNotFound as HTTP404_NotFound
from webob.exc import HTTPFound as HTTP302_Found


# for lazy loading
jinja2 = None


class BasicHandler(webapp2.RequestHandler):
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
            ret[datanodename] = [formatter(x) for x in objects]
        else:
            ret[datanodename] = objects
        return ret

    def render(self, values, template_name):
        """Render a Jinja2 Template"""
        global jinja2
        if not jinja2:
            import jinja2
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(config.template_dirs))
        try:
            template = env.get_template(template_name)
        except TemplateNotFound:
            raise jinja2.TemplateNotFound(template_name)
        myval = dict(uri=self.request.url)
        myval.update(values)
        content = template.render(myval)
        self.response.out.write(content)

    def login_required(self):
        """Returns the currently logged in user."""
        self.session = get_current_session()
        self.credential = None
        if self.session.get('uid'):
            self.credential = memcache.get("cred_%s" % self.session['uid'])
            if self.credential is None:
                self.credential = Credential.get_by_key_name(self.session['uid'])
                memcache.add("cred_%s" % self.session['uid'], self.credential, 300)

        # we don't have an active session
        if not self.credential:
            # no session information - try HTTP - Auth
            uid, secret = None, None
            # see if we have HTTP-Basic Auth Data
            if self.request.headers.get('Authorization'):
                auth_type, encoded = self.request.headers.get('Authorization').split(None, 1)
                if auth_type.lower() == 'basic':
                    uid, secret = encoded.decode('base64').split(':', 1)
                    credential = Credential.get_by_key_name(uid.strip() or ' *invalid* ')
                    if credential and credential.secret == secret.strip():
                        # Siccessful login
                        self.credential = credential
                        self.session['uid'] = credential.uid
                        # Log, but only once every 10h
                        data = memcache.get("login_%s_%s" % (uid, request.remote_addr))
                        if not data:
                            logging.info("API-Login von %s/%s", uid, request.remote_addr)
                            memcache.set("login_%s_%s" % (uid, request.remote_addr), True, 60 * 60 * 10)
                    else:
                        logging.error("failed API-Login von %s/%s", uid, request.remote_addr)

        # HTTP basic Auth failed
        if not self.credential:
            # Login not successfull
            if 'text/html' in self.request.headers.get('Accept', ''):
                # we assume the request came via a browser - redirect to the "nice" login page
                self.response.set_status(302)
                absolute_url = self.abs_url("/_ah/login_required?continue=%s" % urllib.quote(self.request.url))
                self.response.headers['Location'] = str(absolute_url)
                raise HTTP302_Found(location=str(absolute_url))
            else:
                # We assume the access came via cURL et al, request Auth vie 401 Status code.
                self.response.set_status(401)
                self.response.headers['Content-Type'] = 'text/html; charset=utf-8'
                self.response.headers['WWW-Authenticate'] = 'Basic realm="hdEDIhub"'
                self.response.out.write("""<html>
  <head><title>Authentication Required</title></head>
  <body>
    <h1>Authentication Required</h1>
    Can't get in? Stay out!
  </body>
</html>""")
                raise HTTP401_Unauthorized(headers={'WWW-Authenticate': 'Basic realm="API Login'})

        return self.credential
