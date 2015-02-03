#!/usr/bin/env python
# encoding: utf-8
"""
handler.py - default Request Handler

Created by Maximillian Dornseif on 2010-10-03.
Copyright (c) 2010-2015 HUDORA. All rights reserved.
"""


import logging

# Wenn es ein `config` Modul gibt, verwenden wir es, wenn nicht haben wir ein default.
try:
    import config
except (ImportError), msg:
    logging.debug('no config file used because of %s', msg)
    config = object()

LOGIN_ALLOWED_DOMAINS = getattr(config, 'LOGIN_ALLOWED_DOMAINS', [])
config.template_dirs = getattr(config, 'template_dirs', ['./templates'])

import base64
import datetime
import hashlib
import os
import time
import urllib
import urlparse
import uuid
import warnings

from functools import partial
from gaetk import webapp2
import itsdangerous

from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import db, ndb
from webob.exc import HTTPBadRequest as HTTP400_BadRequest
from webob.exc import HTTPConflict as HTTP409_Conflict
from webob.exc import HTTPForbidden as HTTP403_Forbidden
from webob.exc import HTTPFound as HTTP302_Found
from webob.exc import HTTPGone as HTTP410_Gone
from webob.exc import HTTPMethodNotAllowed as HTTP405_HTTPMethodNotAllowed
from webob.exc import HTTPMovedPermanently as HTTP301_Moved
from webob.exc import HTTPNotAcceptable as HTTP406_NotAcceptable
from webob.exc import HTTPNotFound as HTTP404_NotFound
from webob.exc import HTTPNotImplemented as HTTP501_NotImplemented
from webob.exc import HTTPRequestEntityTooLarge as HTTP413_TooLarge
from webob.exc import HTTPSeeOther as HTTP303_SeeOther
from webob.exc import HTTPServerError as HTTP500_ServerError
from webob.exc import HTTPServiceUnavailable as HTTP503_ServiceUnavailable
from webob.exc import HTTPTemporaryRedirect as HTTP307_TemporaryRedirect
from webob.exc import HTTPUnauthorized as HTTP401_Unauthorized
from webob.exc import HTTPUnsupportedMediaType as HTTP415_UnsupportedMediaType

from gaetk.gaesessions import get_current_session
import gaetk.compat


warnings.filterwarnings(
    'ignore',
    'decode_param_names is deprecated and will not be supported starting with WebOb 1.2')

# to mark the exception as being used
_dummy = [HTTP301_Moved, HTTP302_Found, HTTP303_SeeOther, HTTP307_TemporaryRedirect,
          HTTP400_BadRequest, HTTP403_Forbidden, HTTP404_NotFound, HTTP405_HTTPMethodNotAllowed,
          HTTP406_NotAcceptable, HTTP409_Conflict, HTTP410_Gone, HTTP413_TooLarge,
          HTTP415_UnsupportedMediaType, HTTP500_ServerError, HTTP501_NotImplemented,
          HTTP503_ServiceUnavailable]


CREDENTIAL_CACHE_TIMEOUT = 300
_jinja_env_cache = {}


# for import by clients
WSGIApplication = webapp2.WSGIApplication


def login_user(credential, session, via, response=None):
    """Ensure the system knows that a user has been logged in."""
    session['uid'] = credential.uid
    if 'login_via' not in session:
        session['login_via'] = via
    if 'logintime' not in session:
        session['login_time'] = datetime.datetime.now()
    if not os.environ.get('USER_ID', None):
        os.environ['USER_ID'] = credential.uid
        os.environ['AUTH_DOMAIN'] = 'auth.hudora.de'
        # os.environ['USER_IS_ADMIN'] = credential.admin
        if credential.email:
            os.environ['USER_EMAIL'] = credential.email
        else:
            os.environ['USER_EMAIL'] = '%s@auth.hudora.de' % credential.uid
    if response:
        s = itsdangerous.URLSafeTimedSerializer(session.base_key)
        uidcookie = s.dumps(dict(uid=credential.uid))
        host = os.environ.get('HTTP_HOST', '')
        if host.endswith('appspot.com'):
            # setting cookies for .appspot.com does not work
            domain = '.'.join(host.split('.')[-3:])
        else:
            domain = '.'.join(host.split('.')[-2:])
        response.set_cookie('gaetkuid', uidcookie, domain='.%s' % domain, max_age=60 * 60 * 2)


def _get_credential(username):
    """Helper to read Credentials - can be monkey_patched"""
    return NdbCredential.get_by_id(username)


class Credential(db.Expando):
    """Bildet eine Zugriffsberechtigung ab. Legacy"""


class NdbCredential(ndb.Expando):
    """Encodes a user and his permissions."""
    _default_indexed = False
    uid = ndb.StringProperty(required=True)  # == key.id()
    user = ndb.UserProperty(required=False)  # Google (?) User
    tenant = ndb.StringProperty(required=False, default='_unknown', indexed=False)  # hudora.de
    email = ndb.StringProperty(required=False)
    secret = ndb.StringProperty(required=True, indexed=False)  # "Password" - NOT user-settable
    admin = ndb.BooleanProperty(default=False, indexed=False)
    text = ndb.StringProperty(required=False, indexed=False)
    permissions = ndb.StringProperty(repeated=True, indexed=False)
    created_at = ndb.DateTimeProperty(auto_now_add=True)
    updated_at = ndb.DateTimeProperty(auto_now=True)
    created_by = ndb.UserProperty(required=False, auto_current_user_add=True)
    updated_by = ndb.UserProperty(required=False, auto_current_user=True)

    @classmethod
    def _get_kind(cls):
        return 'Credential'

    @classmethod
    def create(cls, uid=None, tenant='_unknown', user=None, admin=False, **kwargs):
        """Creates a credential Object generating a random secret and a random uid if needed."""
        # secret hopfully contains about 64 bits of entropy - more than most passwords
        data = u'%s%s%s%f%s' % (user, uuid.uuid1(), uid, time.time(),
                                os.environ.get('CURRENT_VERSION_ID', '?'))
        digest = hashlib.md5(data.encode('utf-8')).digest()
        secret = str(base64.b32encode(digest).rstrip('='))[1:15]
        if not uid:
            uid = "u%s" % (cls.allocate_ids(1)[0])
        kwargs['permissions'] = ['generic_permission']
        ret = cls.get_or_insert(uid, uid=uid, secret=secret, tenant=tenant,
                                user=user, admin=admin, **kwargs)
        return ret

    def __repr__(self):
        return "<gaetk.NdbCredential %s>" % self.uid


class BasicHandler(webapp2.RequestHandler):
    """Generic Handler functionality.

    provides

    * `self.session` which is based on https://github.com/dound/gae-sessions.
    * `self.login_required()` and `self.is_admin()` for Authentication
    * `self.authchecker()` to be overwritten to fully customize authentication
    """

    # disable session based authentication on demand
    enableSessionAuth = True
    defaultCachingTime = None

    def __init__(self, *args, **kwargs):
        """Initialize RequestHandler"""
        self.credential = None
        try:
            self.session = get_current_session()
        except AttributeError:
            # session middleware might not be enabled
            self.session = {}
        super(BasicHandler, self).__init__(*args, **kwargs)
        self.credential = None

    def abs_url(self, url):
        """Converts an relative into an absolute URL."""
        return urlparse.urljoin(self.request.uri, url)

    def error(self, code):
        """Clears the response output stream and sets the given HTTP error code.

          code: the HTTP status error code (e.g., 501)
        """
        logging.info('Errorhandler')
        super(BasicHandler, self).error(code)
        if str(code) == '404':
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write('Daten nicht gefunden.')

    def paginate(self, query, defaultcount=10, datanodename='objects', calctotal=False, formatter=None):
        """Pagination a la http://mdornseif.github.com/2010/10/02/appengine-paginierung.html

        Returns something like
            {more_objects=True, prev_objects=True,
             prev_start=10, next_start=30,
             objects: [...], cursor='ABCDQWERY'}

        `formatter` is called for each object and can transfor it into something suitable.
        If no `formatter` is given and objects have a `as_dict()` method, this is used
        for formating.

        if `calctotal == True` then the total number of matching rows is given as an integer value. This
        is a ecpensive operation on the AppEngine and results might be capped at 1000.

        `datanodename` is the key in the returned dict, where the Objects resulting form the query resides.

        `defaultcount` is the default number of results returned. It can be overwritten with the
        HTTP-parameter `limit`.

        The `start` HTTP-parameter can skip records at the beginning of the result set.

        If the `cursor` HTTP-parameter is given we assume this is a cursor returned from an earlier query.
        See http://blog.notdot.net/2010/02/New-features-in-1-3-1-prerelease-Cursors and
        http://code.google.com/appengine/docs/python/datastore/queryclass.html#Query_cursor for
        further Information.
        """
        limit = self.request.get_range('limit', min_value=1, max_value=1000, default=defaultcount)

        total = None
        if calctotal:
            # We count up to maximum of 10000. Counting is a somewhat expensive operation on AppEngine
            total = query.count(10000)

        start_cursor = self.request.get('cursor', '')
        if start_cursor:
            objects, cursor, more_objects = gaetk.compat.xdb_fetch_page(
                query, limit, start_cursor=start_cursor)
            start = self.request.get_range('cursor_start', min_value=0, max_value=10000, default=0)
            prev_objects = True
        else:
            start = self.request.get_range('start', min_value=0, max_value=10000, default=0)
            objects, cursor, more_objects = gaetk.compat.xdb_fetch_page(query, limit, offset=start)
            prev_objects = start > 0

        prev_start = max(start - limit - 1, 0)
        next_start = max(start + len(objects), 0)
        clean_qs = dict([(k, self.request.get(k)) for k in self.request.arguments()
                         if k not in ['start', 'cursor', 'cursor_start']])
        ret = dict(more_objects=more_objects, prev_objects=prev_objects,
                   prev_start=prev_start, next_start=next_start,
                   total=total)
        if more_objects:
            ret['cursor'] = cursor.urlsafe()
            ret['cursor_start'] = start + limit
            # query string to get to the next page
            qs = dict(cursor=ret['cursor'], cursor_start=ret['cursor_start'])
            qs.update(clean_qs)
            ret['next_qs'] = urllib.urlencode(qs)
        if prev_objects:
            # query string to get to the next previous page
            qs = dict(start=ret['prev_start'])
            qs.update(clean_qs)
            ret['prev_qs'] = urllib.urlencode(qs)
        if formatter:
            ret[datanodename] = [formatter(x) for x in objects]
        else:
            ret[datanodename] = []
            for obj in objects:
                ret[datanodename].append(obj)
        return ret

    def default_template_vars(self, values):
        """Helper to provide additional values to HTML Templates. To be overwritten in subclasses. E.g.

            def default_template_vars(self, values):
                myval = dict(credential_empfaenger=self.credential_empfaenger,
                             navsection=None)
                myval.update(values)
                return myval
        """
        values.update({'is_admin': self.is_admin()})
        if self.is_admin():
            values.update({'credential': self.credential,
                           'is_admin': self.is_admin()})
        return values

    def create_jinja2env(self, extensions=()):
        """Initialise and return a jinja2 Environment instance.

        Overwrite this method to setup specific behaviour.
        For example, to allow i18n:

            class myHandler(BasicHandler):
                def create_jinja2env(self):
                    import gettext
                    import jinja2
                    env = jinja2.Environment(extensions=['jinja2.ext.i18n'],
                                             loader=jinja2.FileSystemLoader(config.template_dirs))
                    env.install_gettext_translations(gettext.NullTranslations())
                    return env
        """
        import jinja2

        key = tuple(extensions)
        if key not in _jinja_env_cache:
            env = jinja2.Environment(loader=jinja2.FileSystemLoader(config.template_dirs),
                                     extensions=extensions,
                                     auto_reload=True,  # do check if the source changed
                                     trim_blocks=True,  # first newline after a block is removed
                                     bytecode_cache=jinja2.MemcachedBytecodeCache(memcache, timeout=600)
                                     )
            _jinja_env_cache[key] = env
        return _jinja_env_cache[key]

    def rendered(self, values, template_name):
        """Return the rendered content of a Jinja2 Template.

        Per default the template is provided with the `uri` and `credential` variables plus everything
        which is given in `values`.
        """

        import jinja2
        import gaetk.jinja_filters as myfilters

        env = self.create_jinja2env()
        # TODO: do we need that here or in create_jinja2env?
        myfilters.register_custom_filters(env)
        try:
            template = env.get_template(template_name)
        except jinja2.TemplateNotFound:
            # better error reporting - we want to see the name of the base template
            raise jinja2.TemplateNotFound(template_name)
        myval = dict(uri=self.request.url, credential=self.credential)
        myval.update(self.default_template_vars(values))
        self._expire_messages()
        myval.update(dict(_gaetk_messages=self.session.get('_gaetk_messages', [])))
        try:
            content = template.render(myval)
        except jinja2.TemplateNotFound:
            # better error reporting
            logging.info('jinja2 environment: %s', env)
            logging.info('template dirs: %s', config.template_dirs)
            raise

        return content

    def render(self, values, template_name, caching_time=None):
        """Render a Jinja2 Template and write it to the client.

        The parameter `caching_time` describes the number of seconds,
        the result should be cachet at frontend caches.
        None means no Caching-Headers.
        0 or negative Values generate an comand to disable all caching.
        """

        if caching_time is None:
            caching_time = self.defaultCachingTime

        if caching_time is not None:
            if caching_time > 0:
                self.response.headers['Cache-Control'] = 'max-age=%d public' % caching_time
            elif caching_time <= 0:
                self.response.headers['Cache-Control'] = 'no-cache public'

        start = time.time()
        self.response.out.write(self.rendered(values, template_name))
        delta = time.time() - start
        if delta > 500:
            logging.warn("rendering took %d ms", (delta * 1000.0))

    def return_text(self, text, status=200, content_type='text/plain', encoding='utf-8'):
        """Quick and dirty sending of some plaintext to the client."""
        self.response.set_status(status)
        self.response.headers['Content-Type'] = content_type
        if isinstance(text, unicode):
            text = text.encode(encoding)
        self.response.body = text + '\n'

    def _expire_messages(self):
        """Remove Messages already displayed."""
        new = []
        for message in self.session.get('_gaetk_messages', []):
            if message.get('expires', 0) > time.time():
                new.append(message)
        if len(new) != len(self.session.get('_gaetk_messages', [])):
            self.session['_gaetk_messages'] = new

    def multirender(self, fmt, data, mappers=None, contenttypes=None, filename='download',
                    defaultfmt='html', html_template='data', html_addon=None,
                    xml_root='data', xml_lists=None):
        r"""Multirender is meant to provide rendering for a variety of formats with minimal code.
        For the three major formats HTML, XML und JSON you can get away with virtually no code.
        Some real-world view method might look like this:

            # URL matches '/empfaenger/([A-Za-z0-9_-]+)/rechnungen\.?(json|xml|html)?',
            def get(self, kundennr, fmt):
                query = models.Rechnung.all().filter('kundennr = ', kundennr)
                values = self.paginate(query, 25, datanodename='rechnungen')
                self.multirender(fmt, values,
                                 filename='rechnungen-%s' % kundennr,
                                 html_template='rechnungen.html')

        `/empfaenger/12345/rechnungen` and `/empfaenger/12345/rechnungen.html` will result in
        `rechnungen.html` beeing rendered.
        `/empfaenger/12345/rechnungen.json` results in JSON being returned with a
        `Content-Disposition` header sending it to the file `rechnungen-12345.json`. Likewise for
        `/empfaenger/12345/rechnungen.xml`.
        If you add the Parameter `disposition=inline` no Content-Desposition header is generated.

        If you use fmt=json with a `callback` parameter, JSONP is generated. See
        http://en.wikipedia.org/wiki/JSONP#JSONP for details.

        IF you give a dict in `html_addon` this dict is additionaly passed the the HTML rendering function
        (but not to the rendering functions of other formats).

        You can give the `xml_root` and `xml_lists` parameters to provide `huTools.structured.dict2xml()`
        with defenitions on how to name elements. See the documentation of `roottag` and `listnames` in
        dict2xml documentation.

        For more sophisticated layout you can give customized mappers. Using functools.partial
        is very helpfiull for thiss. E.g.

            from functools import partial
            multirender(fmt, values,
                        mappers=dict(xml=partial(dict2xml, roottag='response',
                                                 listnames={'rechnungen': 'rechnung', 'odlines': 'odline'},
                                                  pretty=True),
                                     html=lambda x: '<body><head><title>%s</title></head></body>' % x))
        """

        # We lazy import huTools to keep gaetk usable without hutools
        import huTools.hujson
        import huTools.structured

        # If no format is given, we assume HTML (or whatever is given in defaultfmt)
        # We also provide a list of convinient default content types and encodings.
        fmt = fmt or defaultfmt
        mycontenttypes = dict(pdf='application/pdf',
                              xml="application/xml; encoding=utf-8",
                              json="application/json; encoding=utf-8",
                              html="text/html; encoding=utf-8",
                              csv="text/csv; encoding=utf-8",
                              invoic="application/edifact; encoding=iso-8859-1",
                              desadv="application/edifact; encoding=iso-8859-1")
        if contenttypes:
            mycontenttypes.update(contenttypes)

        # Default mappers are there for XML and JSON (provided by huTools) and HTML provided by Jinja2
        # we provide a default dict2xml renderer based on the xml_* parameters given
        mydict2xml = partial(huTools.structured.dict2xml, roottag=xml_root, listnames=xml_lists, pretty=True)
        # The HTML Render integrates additional data via html_addon
        htmldata = data.copy()
        if html_addon:
            htmldata.update(html_addon)
        htmlrender = lambda x: self.rendered(htmldata, html_template)
        mymappers = dict(xml=mydict2xml,
                         json=huTools.hujson2.dumps,
                         html=htmlrender)
        if mappers:
            mymappers.update(mappers)

        # Check early if we have no corospondending configuration to provide more meaningful error messages.
        if fmt not in mycontenttypes:
            raise ValueError('No content-type for format "%r"' % contenttypes)
        if fmt not in mymappers:
            raise ValueError('No mapper for format "%r"' % fmt)

        # Disposition helps the browser to decide if something should be downloaded to disk or
        # if it should displayed in the browser window. It also can provide a filename.
        # per default we provide downloadable files
        if self.request.get('disposition') != 'inline':
            disposition = "attachment"
        else:
            disposition = "inline"

        if fmt not in ['html', 'json']:
            self.response.headers["Content-Disposition"] = str("%s; filename=%s.%s" % (
                disposition, filename, fmt))
        # If we have gotten a `callback` parameter, we expect that this is a
        # [JSONP](http://en.wikipedia.org/wiki/JSONP#JSONP) can and therefore add the padding
        if self.request.get('callback', None) and fmt == 'json':
            response = "%s (%s)" % (self.request.get('callback', None), mymappers[fmt](data))
            self.response.headers['Content-Type'] = 'text/javascript'
        else:
            self.response.headers['Content-Type'] = mycontenttypes[fmt]
            response = mymappers[fmt](data)
        self.response.out.write(response)

    def is_admin(self):
        """Returns if the currently logged in user is admin"""
        # Google App Engine Administrators
        if users.is_current_user_admin():
            return True
        # Requests from localhost (on dev_appserver) are always admin
        if self.request.remote_addr == '127.0.0.1':
            return True
        # User with Admin permissions via Credential entities
        if not hasattr(self, 'credential'):
            return False
        elif self.credential is None:
            return False
        return getattr(self.credential, 'admin', False)

    def has_permission(self, permission):
        """
        Checks if user has a given permission.

        Returns False, if no user is logged in.
        """
        if self.credential:
            return permission in self.credential.permissions
        return False

    def login_required(self):
        """Returns the currently logged in user and forces login."""

        # Avoid beeing called twice
        if getattr(self.request, '_login_required_called', False):
            return self.credential

        self.credential = None

        # try if we have a session based login
        if self.session.get('uid'):
            self.credential = _get_credential(self.session['uid'])
            if self.credential:
                login_user(self.credential, self.session, 'session', self.response)

        if not self.credential:
            # still no session information - try HTTP - Auth
            uid, secret = None, None
            # see if we have HTTP-Basic Auth Data
            if self.request.headers.get('Authorization'):
                secret, uid = self._parse_authorisation()
                credential = _get_credential(uid.strip() or ' *invalid* ')
                if credential and credential.secret == secret.strip():
                    # Successful login
                    self.credential = credential
                    login_user(self.credential, self.session, 'HTTP', self.response)
                    logging.debug("HTTP-Login from %s/%s", uid, self.request.remote_addr)
                else:
                    logging.error(
                        "failed HTTP-Login from %s/%s %s", uid, self.request.remote_addr,
                        self.request.headers.get('Authorization'))
                    raise HTTP401_Unauthorized(
                        "Invalid HTTP-Auth",
                        headers={'WWW-Authenticate': 'Basic realm="API Login"'})

        # HTTP Basic Auth failed
        # we don't accept login based soley on Google Infrastructure login
        # and channel users through OAuth2 Connect via login.py to get session
        # authentication
        if not self.credential:
            # Login not successful
            is_browser = (
                'text/' in self.request.headers.get('Accept', '')
                or 'image/' in self.request.headers.get('Accept', '')
                or self.request.is_xhr
                or 'Mozilla' in self.request.headers.get('User-Agent', ''))
            if is_browser:
                # we assume the request came via a browser - redirect to the "nice" login page
                # let login.py handle it from there
                absolute_url = self.abs_url(
                    "/_ah/login_required?continue=%s" % urllib.quote(self.request.url))
                raise HTTP302_Found(location=absolute_url)
            else:
                # We assume the access came via cURL et al, request Auth via 401 Status code.
                logging.info("requesting HTTP-Auth %s %s", self.request.remote_addr,
                             self.request.headers.get('Authorization'))
                raise HTTP401_Unauthorized(headers={'WWW-Authenticate': 'Basic realm="API Login"'})

        self.request._login_required_called = True
        return self.credential

    def _parse_authorisation(self):
        """Parse Authorization Header"""
        auth_type, encoded = self.request.headers.get('Authorization').split(None, 1)
        if auth_type.lower() != 'basic':
            raise HTTP400_BadRequest(
                "unknown HTTP-Login type %r %s %s", auth_type, self.request.remote_addr,
                self.request.headers.get('Authorization'))

        decoded = encoded.decode('base64')
        # If the Client send us invalid credentials, let him know , else parse into
        # username and password
        if ':' not in decoded:
            raise HTTP400_BadRequest("invalid credentials %r" % decoded)
        uid, secret = decoded.split(':', 1)
        return secret, uid

    def authchecker(self, method, *args, **kwargs):
        """Function to allow implementing authentication for all subclasses. To be overwritten."""
        pass

    def finished_hook(self, ret, method, *args, **kwargs):
        """Function to allow logging etc. To be overwritten."""
        # not called when exceptions are raised

        # simple sample implementation: check compliance for headers/wsgiref
        for name, val in self.response.headers.items():
            if not (isinstance(name, basestring) and isinstance(val, basestring)):
                logging.error("Header names and values must be strings: {%r: %r} in %s(%r, %r) => %r",
                              name, val, method, args, kwargs, ret)

    def dispatch(self):
        """Dispatches the requested method."""
        request = self.request
        method_name = request.route.handler_method
        if not method_name:
            method_name = webapp2._normalize_handler_method(request.method)

        method = getattr(self, method_name, None)
        if method is None:
            # 405 Method Not Allowed.
            # The response MUST include an Allow header containing a
            # list of valid methods for the requested resource.
            # http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html#sec10.4.6
            methods = []
            for method in ('GET', 'POST', 'HEAD', 'OPTIONS', 'PUT', 'DELETE', 'TRACE'):
                if getattr(self, webapp2._normalize_handler_method(method), None):
                    methods.append(method)
            valid = ', '.join(methods)
            self.abort(405, headers=[('Allow', valid)])

        # The handler only receives *args if no named variables are set.
        args, kwargs = request.route_args, request.route_kwargs
        if kwargs:
            args = ()

        # bind session on dispatch (not in __init__)
        try:
            self.session = get_current_session()
        except AttributeError:
            # session handling not activated
            self.session = {}
        # init messages array based on session
        self.session['_gaetk_messages'] = self.session.get('_gaetk_messages', [])
        # Give authentication Hooks opportunity to do their thing
        self.authchecker(method, *args, **kwargs)

        ret = method(*args, **kwargs)
        self.finished_hook(ret, method, *args, **kwargs)
        return ret

    def add_message(self, typ, html, ttl=15):
        """Sets a user specified message to be displayed to the currently logged in user.

        `type` can be `error`, `success`, `info` or `warning`
        `html` is the text do be displayed
        `ttl` is the number of seconds after we should stop serving the message."""
        messages = self.session.get('_gaetk_messages', [])
        messages.append(dict(type=typ, html=html, expires=time.time() + ttl))
        # We can't use `.append()` because this doesn't result in automatic session saving.
        self.session['_gaetk_messages'] = messages


class JsonResponseHandler(BasicHandler):
    """Handler which is specialized for returning JSON.

    Excepts the method to return

    * dict(), e.g. `{'foo': bar}`
    * (dict(), int status), e.g. `({'foo': bar}, 200)`
    * (dict(), int status, int cachingtime), e.g. `({'foo': bar}, 200, 86400)`

    Dict is converted to JSON. `status` is used as HTTP status code. `cachingtime`
    is used to generate a `Cache-Control` header. If `cachingtime is None`, no header
    is generated. `cachingtime` defaults to 60 seconds.
    """
    # Our default caching is 60s
    default_cachingtime = 60

    def serialize(self, content):
        """convert content to JSON."""
        import huTools.hujson2
        return huTools.hujson2.dumps(content)

    def dispatch(self):
        """Dispatches the requested method."""

        request = self.request
        method_name = request.route.handler_method
        if not method_name:
            method_name = webapp2._normalize_handler_method(request.method)

        method = getattr(self, method_name, None)
        if method is None:
            # 405 Method Not Allowed.
            # The response MUST include an Allow header containing a
            # list of valid methods for the requested resource.
            # http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html#sec10.4.6
            valid = ', '.join(webapp2._get_handler_methods(self))
            self.abort(405, headers=[('Allow', valid)])

        # The handler only receives *args if no named variables are set.
        args, kwargs = request.route_args, request.route_kwargs
        if kwargs:
            args = ()

        # bind session on dispatch (not in __init__)
        self.session = get_current_session()
        # init messages array based on session
        self.session['_gaetk_messages'] = self.session.get('_gaetk_messages', [])
        # Give authentication Hooks opportunity to do their thing
        self.authchecker(method, *args, **kwargs)

        # Execute the method.
        reply = method(*args, **kwargs)

        # find out which return convention was used - first set defaults ...
        content = reply
        statuscode = 200
        cachingtime = self.default_cachingtime
        # ... then check if we got a 2-tuple reply ...
        if isinstance(reply, tuple) and len(reply) == 2:
            content, statuscode = reply
        # ... or a 3-tuple reply.
        if isinstance(reply, tuple) and len(reply) == 3:
            content, statuscode, cachingtime = reply
        # Finally begin sending the response
        response = self.serialize(content)
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
        self.response.out.write('\n')
