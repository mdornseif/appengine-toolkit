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
from gaetk.gaesessions import get_current_session
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import webapp
from webob.exc import HTTPBadRequest as HTTP400_BadRequest
from webob.exc import HTTPForbidden as HTTP403_Forbidden
from webob.exc import HTTPFound as HTTP302_Found
from webob.exc import HTTPNotFound as HTTP404_NotFound
from webob.exc import HTTPRequestEntityTooLarge as HTTP413_TooLarge
from webob.exc import HTTPUnauthorized as HTTP401_Unauthorized
import logging
import urllib
import urlparse
import uuid
import base64
import hashlib

# for lazy loading
jinja2 = None


CRED_CACHE_TIMEOUT = 600


class Credential(db.Expando):
    """Represents an access token and somebody who is allowed to use it.

    Credentials MIGHT map to a google user object
    """
    tenant = db.StringProperty(required=False, default='_unknown')
    email = db.EmailProperty(required=False)
    user = db.UserProperty(required=False)
    uid = db.StringProperty(required=True)
    secret = db.StringProperty(required=True)
    text = db.StringProperty(required=False)
    admin = db.BooleanProperty(default=False)
    created_at = db.DateTimeProperty(auto_now_add=True)
    updated_at = db.DateTimeProperty(auto_now=True)
    created_by = db.UserProperty(required=False, auto_current_user_add=True)
    updated_by = db.UserProperty(required=False, auto_current_user=True)

    @classmethod
    def create(cls, tenant='_unknown', user=None, uid=None, text='', email=None, admin=False):
        """Creates a credential Object generating a random secret and a random uid if needed."""
        # secret hopfully contains about 64 bits of entropy - more than most passwords
        data = "%s%s%s%s%s" % (user, uuid.uuid1(), uid, text, email)
        secret = str(base64.b32encode(hashlib.md5(data).digest()).rstrip('='))[1:15]
        if not uid:
            handmade_key = db.Key.from_path('Credential', 1)
            uid = "u%s" % (db.allocate_ids(handmade_key, 1)[0])
        instance = cls.get_or_insert(key_name=uid, uid=uid, secret=secret, tenant=tenant,
                                     user=user, text=text, email=email, admin=admin)
        return instance

    def __repr__(self):
        return "<gaetk.Credential %s>" % self.uid


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

        `formatter` is called for each object and can transfor it into something suitable.
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
        except jinja2.TemplateNotFound:
            raise jinja2.TemplateNotFound(template_name)
        myval = dict(uri=self.request.url)
        myval.update(values)
        content = template.render(myval)
        self.response.out.write(content)

    def login_required(self, deny_localhost=False):
        """Returns the currently logged in user and forces login.

        Access from 127.0.0.1 is alowed without authentication if deny_localhost is false.
        """

        self.session = get_current_session()
        self.credential = None
        if self.session.get('uid'):
            self.credential = memcache.get("cred_%s" % self.session['uid'])
            if self.credential is None:
                self.credential = Credential.get_by_key_name(self.session['uid'])
                memcache.add("cred_%s" % self.session['uid'], self.credential, CRED_CACHE_TIMEOUT)

        # we don't have an active session
        if not self.credential:
            # no session information - try HTTP - Auth
            uid, secret = None, None
            # see if we have HTTP-Basic Auth Data
            if self.request.headers.get('Authorization'):
                auth_type, encoded = self.request.headers.get('Authorization').split(None, 1)
                if auth_type.lower() == 'basic':
                    uid, secret = encoded.decode('base64').split(':', 1)
                    credential = memcache.get("cred_%s" % uid)
                    if not credential:
                        credential = Credential.get_by_key_name(uid.strip() or ' *invalid* ')
                        memcache.add("cred_%s" % uid, credential, CRED_CACHE_TIMEOUT)
                    if credential and credential.secret == secret.strip():
                        # Successful login
                        self.credential = credential
                        self.session['uid'] = credential.uid
                        # Log, but only once every 10h
                        data = memcache.get("login_%s_%s" % (uid, self.request.remote_addr))
                        if not data:
                            memcache.set("login_%s_%s" % (uid, self.request.remote_addr), True, 60 * 60 * 10)
                            logging.info("HTTP-Login from %s/%s", uid, self.request.remote_addr)
                    else:
                        logging.error("failed HTTP-Login from %s/%s %s", uid, self.request.remote_addr,
                                       self.request.headers.get('Authorization'))
                else:
                    logging.error("unknown HTTP-Login type %r %s %s", auth_type, self.request.remote_addr,
                                   self.request.headers.get('Authorization'))

        # HTTP Basic Auth failed
        if not self.credential:
            if (self.request.remote_addr == '127.0.0.1') and not deny_localhost:
                # for testing we allow unauthenticted access from localhost
                pass
            else:
                # Login not successfull
                if 'text/html' in self.request.headers.get('Accept', ''):
                    # we assume the request came via a browser - redirect to the "nice" login page
                    self.response.set_status(302)
                    absolute_url = self.abs_url("/_ah/login_required?continue=%s" % urllib.quote(self.request.url))
                    self.response.headers['Location'] = str(absolute_url)
                    raise HTTP302_Found(location=str(absolute_url))
                else:
                    # We assume the access came via cURL et al, request Auth vie 401 Status code.
                    logging.debug("requesting HTTP-Auth %s %s", self.request.remote_addr,
                                  self.request.headers.get('Authorization'))
                    raise HTTP401_Unauthorized(headers={'WWW-Authenticate': 'Basic realm="API Login"'})

        return self.credential

class JsonResponseHandler(BasicHandler):
    """Handler which is specialized for returning JSON.
    
    Excepts the method to return
    
    * dict(), e.g. `{'foo': bar}`
    * (dict(), int status), e.g. `({'foo': bar}, 200)`
    * (dict(), int status, int cachingtime), e.g. `({'foo': bar}, 200, 86400)`

    Dict is converted to JSON. `status` is used as HTTP status code. `cachingtime`
    is used to generate a `Cache-Control` header. If `cachingtime is None`, no header
    is generated. `cachingtime` defaults to two hours.
    """

    def __call__(self, _method, *args, **kwargs):
        """Dispatches the requested method. """

        # Lazily import hujson to allow using the other classes in this module to be used without
        # huTools beinin installed.
        import huTools.hujson

        # Find Method to be called.
        method = getattr(self, _method, None)
        if method is None:
            # No Mehtod is found.
            # Answer will be `405 Method Not Allowed`.
            # The response MUST include an Allow header containing a
            # list of valid methods for the requested resource.
            # http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html#sec10.4.6
            # so get a lsit of valid Methods and send them back.
            valid = ', '.join(get_valid_methods(self))
            # `self.abort()` will raise an Exception thus exiting this function
            self.abort(405, headers=[('Allow', valid)])

        # Execute the method.
        reply = method(*args, **kwargs)

        # find out which return convention was used - first set defaults ...
        content = reply
        statuscode = 200
        cachingtime = (60 * 60 * 2)
        # ... then check if we got a 2-tuple reply ...
        if isinstance(reply, tuple) and len(reply) == 2:
            content, statuscode = reply
        # ... or a 3-tuple reply.
        if isinstance(reply, tuple) and len(reply) == 3:
            content, statuscode, cachingtime = reply

        # Finally begin sending the response
        response = huTools.hujson.dumps(content)
        if cachingtime:
            self.response.headers['Cache-Control'] = 'max-age=%d, public' % cachingtime
        # If we have gotten a `callback` parameter, we expect that this is a
        # [JSONP](http://en.wikipedia.org/wiki/JSONP#JSONP) cann and therefore add the padding
        if self.request.get('callback', None):
            response = "%s (%s)" % (self.request.get('callback', None), response)
            self.response.headers['Content-Type'] = 'text/javascript'
        else:
            self.response.headers['Content-Type'] = 'application/json'
        # Set status code and write JSON to output stream
        self.response.set_status(statuscode)
        self.response.out.write(response)

