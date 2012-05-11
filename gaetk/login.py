#!/usr/bin/env python
# encoding: utf-8
"""
login.py - login handler for appengine. See handler.py and README.markdown/Authentication
for further Information.

In app.yaml add:

    handlers:
    - url: /_ah/login_required
      script: lib/gaetk/gaetk/login.py
    - url: /logout
      script: lib/gaetk/gaetk/login.py

Created by Maximillian Dornseif on 2010-09-24.
Copyright (c) 2010 HUDORA. All rights reserved.
"""

# pylint can't handle db.Model.get()
# pylint: disable=E1103

import config
config.imported = True

import logging

import gaetk
import huTools.hujson
from gaetk.handler import Credential, create_credential_from_federated_login
from gaetk.gaesessions import get_current_session
from gaetk.handler import BasicHandler
from google.appengine.api import users


try:
    LOGIN_ALLOWED_DOMAINS = config.LOGIN_ALLOWED_DOMAINS
except AttributeError:
    LOGIN_ALLOWED_DOMAINS = []


def get_verified_credential(username, password, session=None):
    """Get a credential object

    The credential object for the given username...
    Otherwise, None is returned.
    """
    # TODO: Add memcache layer, like in gaetk.handler.BasicHandler.login_required
    credential = Credential.get_by_key_name(username)
    if credential and credential.secret == password:
        if session:
            session['uid'] = credential.uid
            session['email'] = credential.email
        return credential


class OpenIdLoginHandler(BasicHandler):
    """Handler for Login"""

    def __init__(self, *args, **kwargs):
        """Initialize handler instance"""

        super(OpenIdLoginHandler, self).__init__(*args, **kwargs)

        # clean previous session
        self.session = get_current_session()
        self.session.regenerate_id()
        if self.session.is_active():
            self.session.terminate()

    def get(self):
        """Handler for Federated login consumer (OpenID) AND HTTP-Basic-Auth.

        For information on OpenID, see http://code.google.com/appengine/articles/openid.html"""

        continue_url = self.request.GET.get('continue', '/')

        # check if we are logged in via OpenID
        user = users.get_current_user()
        if user:
            # yes, there is an active OpenID session
            # user.federated_provider() == 'https://www.google.com/a/hudora.de/o8/ud?be=o8'
            logging.info(u'login: User logged in via OpenID: %s', user)
            if not user.federated_provider():
                # development server
                apps_domain = user.email().split('@')[-1].lower()
            else:
                apps_domain = user.federated_provider().split('/')[4].lower()
            username = user.email()
            credential = Credential.get_by_key_name(username)
            if not credential or not credential.uid == username:
                # So far we have no Credential entity for that user, create one by calling a factory function
                fnc = getattr(config, 'LOGIN_OPENID_CREDENTIAL_CREATOR',
                              create_credential_from_federated_login)
                credential = fnc(user, apps_domain)

            self.session['uid'] = credential.uid
            self.session['email'] = username
            self.response.set_cookie('gaetkopid', apps_domain, max_age=7776000)
            self.redirect(continue_url)
            return

        # If the form data contains hints about an allowed (OpenID) domain, try to login the user via OpenID
        for domain in LOGIN_ALLOWED_DOMAINS:
            if self.request.GET.get('%s.x' % domain):
                openid_url = 'https://www.google.com/accounts/o8/site-xrds?hd=%s' % domain
                logging.info(u'login: OpenID login requested to %s', openid_url)
                # Hand over Authentication Processing to Google/OpenID
                self.redirect(users.create_login_url(continue_url, None, openid_url))
                return

        # If it was impossible to authenticate via OpenID so far,
        # the user is tried to be authenticated via a username-password based approach.
        # The data is either taken from the HTTP header `Authorization` or the provided (form) data.

        msg = ''
        username, password = None, None
        # First, try HTTP basic auth (see RFC 2617)
        if self.request.headers.get('Authorization'):
            auth_type, encoded = self.request.headers.get('Authorization').split(None, 1)
            if auth_type.lower() == 'basic':
                username, password = encoded.decode('base64').split(':', 1)
        # Next, try to get data from the request parameters (form data)
        else:
            username = self.request.get('username', '').strip()
            password = self.request.get('password', '').strip()

        # Verify submitted username and password
        if username:
            credential = get_verified_credential(username, password, session=self.session)
            if credential:
                logging.info(u'login: Login by %s/%s, redirect to %s',
                             username, self.request.remote_addr, continue_url)
                self.redirect(continue_url)
                return
            else:
                logging.warning(u'login: Invalid password for %s', username)
                msg = u'Anmeldung fehlgeschlagen'

        # Last attempt: If there's a cookie which contains the OpenID domain, try to login the user
        domain = self.request.cookies.get('gaetkopid', '')
        if domain in LOGIN_ALLOWED_DOMAINS:
            logging.info(u'login: automatically OpenID login to %s', domain)
            openid_url = 'https://www.google.com/accounts/o8/site-xrds?hd=%s' % domain
            # Hand over Authentication Processing to Google/OpenID
            self.redirect(users.create_login_url(continue_url, None, openid_url))
            return

        # Render template with login form
        self.render({'continue': continue_url, 'domains': LOGIN_ALLOWED_DOMAINS, 'msg': msg}, 'login.html')

    def post(self):
        """Login via Form POST

        Unline the handler for the GET method, this handler only tries
        to authenticate a 'user' by checking a username/password combination
        that was submitted through a form.
        Returns a JSON encoded object with the attribute 'success'.
        """

        if 'username' in self.request.params:
            username = self.request.get('username', '').strip()
            password = self.request.get('password', '').strip()
            credential = get_verified_credential(username, password, self.session)
            if credential:
                logging.info(u'Login by %s/%s', username, self.request.remote_addr)
                response = {'success': True}
            else:
                logging.warning(u'Invalid password for %s:%s', username, password)
                response = {'success': False}
        else:
            response = {'success': False}
        self.response.out.write(huTools.hujson.dumps(response))


class LogoutHandler(OpenIdLoginHandler):
    """Handler for Logout functionality"""

    def get(self):
        """Logout user and terminate the current session"""

        session = get_current_session()
        session['uid'] = None
        if session.is_active():
            session.terminate()

        # log out OpenID and either redirect to 'continue' or display
        # the default logout confirmation page
        continue_url = self.request.get('continue')

        user = users.get_current_user()
        if user:
            path = self.request.path
            self.redirect(users.create_logout_url(path))
        else:
            if continue_url:
                self.redirect(continue_url)
            else:
                self.render({}, 'logout.html')


application = gaetk.webapp2.WSGIApplication([('.*/logout', LogoutHandler),
                                             ('.*', OpenIdLoginHandler),
                                            ])


def main():
    """WSGI Main Entry Point"""
    application.run()


if __name__ == '__main__':
    main()
