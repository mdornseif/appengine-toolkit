#!/usr/bin/env python
# encoding: utf-8
"""
spezifische Login und Logout Funktionalität.

based on EDIhub:login.py

Created by Maximillian Dornseif on 2010-09-24.
Copyright (c) 2010, 2014, 2015 HUDORA. All rights reserved.
"""


config = object()
try:
    import config
except ImportError:
    pass
config.imported = True

import logging
import random
import string
import urllib
import base64
import unicodedata
import json
import os

import huTools.http
import huTools.hujson2
from google.appengine.api import users

import gaetk.handler
from gaetk.handler import BasicHandler
from gaetk.handler import HTTP302_Found

try:
    LOGIN_ALLOWED_DOMAINS = config.LOGIN_ALLOWED_DOMAINS
except AttributeError:
    LOGIN_ALLOWED_DOMAINS = []


def _create_credential(*args, **kwargs):
    """Can be monkeypatched"""
    return gaetk.handler.NdbCredential.create(*args, **kwargs)


class LoginHandler(BasicHandler):
    """Handler for Login"""

    def __init__(self, *args, **kwargs):
        """Initialize handler instance"""

        super(LoginHandler, self).__init__(*args, **kwargs)

    def get_verified_credential(self, uid, secret, session):
        """Get a credential object

        The credential object for the given `uid` matching
        `secret`.
        Otherwise, None is returned.
        """
        credential = gaetk.handler._get_credential(uid)
        if credential and credential.secret == secret:
            gaetk.handler.login_user(credential, session, "uid:secret", self.response)
            return credential

    def get(self):
        """Handler for Form and HTTP-Basic-Auth."""

        continue_url = self.request.GET.get('continue', '/').encode('ascii', 'ignore')

        if not self.request.url.startswith("https://"):
            raise gaetk.handler.HTTP302_Found(location=self.request.url.replace('http://', 'https://', 1))


        if self.request.cookies.get('gaetkuid', None):
            # try single sign on via a different hudora.de domain
            logging.debug("gaetkuid = %r", self.request.cookies.get('gaetkuid', None))
            import itsdangerous
            s = itsdangerous.URLSafeTimedSerializer(self.session.base_key)
            decoded_payload = None
            try:
                decoded_payload = s.loads(
                    self.request.cookies.get('gaetkuid', None),
                    max_age=60 * 60 * 2)
                # This payload is decoded and safe
                logging.info("%r", decoded_payload)
            except itsdangerous.BadSignature:
                logging.warn("BadSignature")
            except itsdangerous.SignatureExpired:
                logging.warn("SignatureExpired")
            if decoded_payload and 'uid' in decoded_payload:
                credential = gaetk.handler._get_credential(decoded_payload['uid'])
                if credential:
                    logging.info("logged in wia SSO %s", decoded_payload.get('provider', '?'))
                    gaetk.handler.login_user(credential, self.session, 'SSO', self.response)
                    raise gaetk.handler.HTTP302_Found(location=continue_url)

        # the user is tried to be authenticated via a username-password based approach.
        # The data is either taken from the HTTP header `Authorization` or the provided (form) data.
        msg = ''
        via = '?'
        username, password = None, None
        # First, try HTTP basic auth (see RFC 2617)
        if self.request.headers.get('Authorization'):
            auth_type, encoded = self.request.headers.get('Authorization').split(None, 1)
            if auth_type.lower() == 'basic':
                username, password = encoded.decode('base64').split(':', 1)
                via = 'HTTP'
        # Next, try to get data from the request parameters (form data)
        else:
            username = self.request.get('username', '').strip()
            password = self.request.get('password', '').strip()
            via = 'FORM'

        # Verify submitted username and password
        if username:
            credential = self.get_verified_credential(username, password, self.session)
            if credential:
                logging.debug(u'login: Login by %s/%s, redirect to %s',
                              username, self.request.remote_addr, continue_url)
                gaetk.handler.login_user(credential, self.session, via, self.response)
                raise gaetk.handler.HTTP302_Found(location=continue_url)
            else:
                logging.warning(u'login: Invalid password for %s', username)
                msg = u'Anmeldung fehlgeschlagen, versuchen Sie es erneut.'

        # Render template with login form
        self.session['continue_url'] = continue_url
        self.render({'continue': continue_url,
                     'domains': LOGIN_ALLOWED_DOMAINS,
                     'oauth_url': get_oauth_url(self.session, self.request),
                     'msg': msg}, 'login.html')

    def post(self):
        """Login via Form POST

        Unlike the handler for the GET method, this handler only tries
        to authenticate a 'user' by checking a username/password combination
        that was submitted through a form.
        Returns a JSON encoded object with the attribute 'success'.
        """

        if 'username' in self.request.params:
            username = self.request.get('username', '').strip()
            password = self.request.get('password', '').strip()
            credential = self.get_verified_credential(username, password, self.session)
            if credential:
                logging.info(u'Login by %s/%s', username, self.request.remote_addr)
                response = {'success': True}
            else:
                logging.warning(u'Invalid password for %s:%s', username, password)
                response = {'success': False}
        else:
            response = {'success': False}
        self.response.out.write(huTools.hujson2.dumps(response))


def get_oauth_url(session, request):
    # Create a state token to prevent request forgery.
    # Store it in the session for later validation.
    if 'oauth_state' not in session:
        state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                        for x in xrange(32))
        session['oauth_state'] = state
    # Set the client ID, token state, and application name in the HTML while
    # serving it.
    url = config.OAUTH['web']['auth_uri']
    params = dict(
        client_id=config.OAUTH['web']['client_id'],
        response_type="code",
        scope="openid email profile",
        redirect_uri=get_oauth_callback_url(request),
        state=session['oauth_state'],
        # login_hint="jsmith@example.com", TODO: gaetkoauthmail
    )
    if len(LOGIN_ALLOWED_DOMAINS) == 1:
        params['hd'] = LOGIN_ALLOWED_DOMAINS[0]

    # intf you know the user's email address, include it in the authentication
    # URI as the value of the login_hint parameter. If you do not include a
    # login_hint and the user is signed into Google with multiple accounts,
    # they will see an "account chooser" asking them to select one account.
    # This might be surprising to them, and they might select an account other
    # than the one your application is trying to authorize, which could
    # increase the complexity of your task.

    return '?'.join([url, urllib.urlencode(params)])


def get_oauth_callback_url(request):
    url = request.host_url + '/gaetk/auth/oauth2callback'
    if url not in config.OAUTH['web']['redirect_uris']:
        logging.debug("%s not valid", url)
        url = 'https://' + os.environ.get('SERVER_NAME') + '/gaetk/auth/oauth2callback'
    if url not in config.OAUTH['web']['redirect_uris']:
        logging.debug("%s not valid", url)
        url = 'https://' + os.environ.get('DEFAULT_VERSION_HOSTNAME') + '/gaetk/auth/oauth2callback'
    if url not in config.OAUTH['web']['redirect_uris']:
        logging.debug("%s not valid", url)
        url = config.OAUTH['web']['redirect_uris'][0]
    return url


class OAuth2Callback(BasicHandler):
    """Handler for Login"""

    def create_credential_oauth2(self, jwt):
        """Create a new credential object for a newly logged in Google user."""

        if jwt.get('email_verified'):
            uid = jwt['email']
        else:
            uid = jwt['sub'] + '#google.' + jwt['hd']
        return _create_credential(
            tenant=jwt['hd'],
            uid=uid,
            admin=True,
            text='created via OAuth2',
            email=jwt['email'],
        )

    def get(self):
        # see http://filez.foxel.org/0F1Z1m282B1M
        # logging.debug("p = %r", self.request.params)
        # https://dev-md-dot-hudoraexpress.appspot.com/oauth2callback?

        continue_url = self.session.pop('continue_url', '/')

        # 3. Confirm anti-forgery state token
        if self.request.get('state') != self.session.get('oauth_state'):
            logging.warn("wrong state: %r != %r" % (
                self.request.get('state'), self.session.get('oauth_state')))
            self.session.terminate()
            raise HTTP302_Found(location=continue_url)

        if LOGIN_ALLOWED_DOMAINS and self.request.get('hd') not in LOGIN_ALLOWED_DOMAINS:
            raise RuntimeError("wrong domain: %r not in %r" % (
                self.request.get('hd'), LOGIN_ALLOWED_DOMAINS))

        # 4. Exchange code for access token and ID token
        url = config.OAUTH['web']['token_uri']
        # get token
        params = dict(
            code=self.request.get('code'),
            client_id=config.OAUTH['web']['client_id'],
            client_secret=config.OAUTH['web']['client_secret'],
            redirect_uri=get_oauth_callback_url(self.request),
            grant_type="authorization_code")
        data = huTools.http.fetch_json2xx(url, method='POST', content=params)
        input_jwt = data['id_token'].split('.')[1]
        input_jwt = unicodedata.normalize('NFKD', input_jwt).encode('ascii', 'ignore')
        # Append extra characters to make original string base 64 decodable.
        input_jwt += '=' * (4 - (len(input_jwt) % 4))
        jwt = base64.urlsafe_b64decode(input_jwt)
        jwt = json.loads(jwt)
        logging.info("jwt = %r", jwt)
        # email_verified True if the user's e-mail address has been verified
        assert jwt['iss'] == 'accounts.google.com'
        assert jwt['aud'] == config.OAUTH['web']['client_id']
        assert jwt['hd'] in LOGIN_ALLOWED_DOMAINS
        # note that the user is logged in

        # hd FEDERATED_IDENTITY FEDERATED_PROVIDER
        for name in 'USER_EMAIL USER_ID USER_IS_ADMIN USER_NICKNAME USER_ORGANIZATION'.split():
            logging.info("%s: %r", name, os.environ.get(name))

        credential = self.create_credential_oauth2(jwt)
        gaetk.handler.login_user(credential, self.session, 'OAuth2', self.response)
        self.response.set_cookie('gaetkoauthmail', jwt['email'], max_age=7776000)

        raise HTTP302_Found(location=users.create_login_url(continue_url))


class LogoutHandler(gaetk.handler.BasicHandler):
    """Handler for Logout functionality"""

    def get(self):
        """Logout user and terminate the current session"""

        logging.info("forcing logout")
        self.session['uid'] = None
        if self.session.is_active():
            self.session.terminate()
        self.session.regenerate_id()

        # log out Google and either redirect to 'continue' or display
        # the default logout confirmation page
        continue_url = self.request.get('continue', '')

        # delete coockies
        self.response.delete_cookie('_ga')  # Appengine Login?
        self.response.delete_cookie('_gat')  # Appengine Login?
        self.response.delete_cookie('SACSID')  # Appengine Login
        self.response.delete_cookie('ACSID')  # Appengine Login
        self.response.delete_cookie('gaetkoauthmail')  # gaetk Login
        self.response.delete_cookie('gaetkuid')  # gaetk Login

        user = users.get_current_user()
        if user:
            logging.info("Google User %s", user)
            path = self.request.path
            logout_url = users.create_logout_url(path)
            logging.info("logging out via %s", logout_url)
            self.redirect(logout_url)
        else:
            if continue_url:
                self.redirect(continue_url)
            else:
                self.render({}, 'logout.html')


class Debug(gaetk.handler.BasicHandler):
    """Handler for Logout functionality"""

    def get(self):
        """Logout user and terminate the current session"""
        self.login_required()
        env = {}
        attrs = ['AUTH_DOMAIN',
                 'USER_EMAIL', 'USER_ID', 'USER_IS_ADMIN',
                 'USER_NICKNAME', 'USER_ORGANIZATION',
                 'FEDERATED_IDENTITY', 'FEDERATED_PROVIDER']
        for name in attrs:
            env[name] = os.environ.get(name)
            logging.info("%s: %r", name, os.environ.get(name))

        logging.debug("headers=%s", self.request.headers)

        self.render(dict(
            env=env,
            google_user=users.get_current_user(),
            credential=self.credential,
            uid=self.session.get('uid'),
        ), 'login_debug.html')


class CredentialsHandler(gaetk.handler.BasicHandler):
    """Credentials - generate or update"""

    def authchecker(self, *args, **kwargs):
        """Only admin users are allowed to access credentials"""
        self.login_required()
        if not self.credential.admin:
            gaetk.handler.HTTP403_Forbidden()

    def get(self):
        """Returns information about the credential referenced by parameter `uid`"""
        uid = self.request.get('uid')
        if not uid:
            raise gaetk.handler.HTTP404_NotFound

        credential = gaetk.handler._get_credential(uid)
        if credential is None:
            raise gaetk.handler.HTTP404_NotFound

        self.response.headers["Content-Type"] = "application/json"
        self.response.out.write(huTools.hujson2.dumps(dict(uid=credential.uid,
                                                           admin=credential.admin, text=credential.text,
                                                           tenant=credential.tenant, email=credential.email,
                                                           permissions=credential.permissions,
                                                           created_at=credential.created_at,
                                                           updated_at=credential.updated_at)))

    def post(self):
        """Use it like this

            curl -u $uid:$secret -X POST -F admin=True \
                -F text='fuer das Einspeisen von SoftM Daten' -F email='edv@shpuadmora.de' \
                http://example.appspot.com/gaetk/credentials
            {
             "secret": "aJNKCDUZW5PIBT23LYX7XXVFENA",
             "uid": "u66666o26ec4b"
            }
        """

        # The data can be submitted either as a json encoded body or form encoded
        if self.request.headers.get('Content-Type', '').startswith('application/json'):
            data = huTools.hujson2.loads(self.request.body)
        else:
            data = self.request

        admin = str(data.get('admin', '')).lower() == 'true'
        text = data.get('text', '')
        uid = data.get('uid')
        email = data.get('email')
        tenant = data.get('tenant')
        permissions = data.get('permissions', '')
        if isinstance(permissions, basestring):
            permissions = permissions.split(',')

        if uid:
            credential = gaetk.handler._get_credential(uid)
        else:
            credential = None

        if credential:
            # if a credential already exists we only have to modify it
            credential.admin = admin
            credential.text = text
            credential.tenant = tenant
            credential.email = email
            credential.permissions = []
            for permission in permissions:
                if permission not in getattr(config, 'ALLOWED_PERMISSIONS', []):
                    raise gaetk.handler.HTTP400_BadRequest("invalid permission %r" % permission)
                credential.permissions.append(permission)
            credential.put()
        else:
            # if not, we generate a new one
            credential = gaetk.handler.NdbCredential.create(
                admin=admin, text=text,
                tenant=tenant, email=email)

        self.response.headers["Content-Type"] = "application/json"
        self.response.set_status(201)
        self.response.out.write(huTools.hujson.dumps(dict(
            uid=credential.uid, secret=credential.secret,
            admin=credential.admin, text=credential.text,
            tenant=credential.tenant, email=credential.email,
            permissions=credential.permissions,
            created_at=credential.created_at,
            updated_at=credential.updated_at)))


# die URL-Handler fuer's Login/ Logout
application = gaetk.webapp2.WSGIApplication([
    ('/gaetk/auth/logout', LogoutHandler),
    ('/gaetk/auth/oauth2callback', OAuth2Callback),
    ('/gaetk/auth/debug', Debug),
    ('/gaetk/auth/credentials', CredentialsHandler),
    ('.*', LoginHandler),
], debug=False)
