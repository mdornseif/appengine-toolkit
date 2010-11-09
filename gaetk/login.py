#!/usr/bin/env python
# encoding: utf-8
"""
login.py - login handler for appengine

Created by Maximillian Dornseif on 2010-09-24.
Copyright (c) 2010 HUDORA. All rights reserved.
"""

# pylint can't handle db.Model.get()
# pylint: disable=E1103

import config
config.imported = True

from ablage.models import Credential
from gaetk import webapp2
from gaetk.gaesessions import get_current_session
from gaetk.handler import BasicHandler
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import logging

ALLOWED_DOMAINS = config.LOGIN_ALLOWED_DOMAINS


class OpenIdLoginHandler(BasicHandler):
    def get(self):
        """Handler for Federated login consumer (OpenID)

        See http://code.google.com/appengine/articles/openid.html"""
        continue_url = self.request.GET.get('continue', '/')
        openid_url = None
        session = get_current_session()
        # clean previous session
        if session.is_active():
            session.terminate()

        # check if we are logged in via OpenID
        user = users.get_current_user()
        logging.info('Google user = %s', user)
        if user:
            #yes
            # assert user.federated_provider() == 'https://www.google.com/a/hudora.de/o8/ud?be=o8'
            username = user.email()
            credential = Credential.get_by_key_name(username)
            if not credential or not credential.uid == username:
                # So far we have no Credential entity for that user, create one
                credential = Credential.create('CYLGI', user=user, uid=username, email=user.email(),
                    text="Automatisch durch OpenID %s angelegt" % user.federated_provider()) #  ,admin=True)
            session['uid'] = credential.uid
            self.redirect(continue_url)
            return

        # we returned from the login form - did the user request OpenID login?
        for domain in ALLOWED_DOMAINS:
            if self.request.GET.get('%s.x' % domain):
                openid_url = 'https://www.google.com/accounts/o8/site-xrds?hd=%s' % domain
        if openid_url:
            logging.info("Openid login requested to %s", openid_url)

        if openid_url:
            # Hand over Authentication Processing to Google/OpenID
            self.redirect(users.create_login_url(continue_url, None, openid_url))
            return
        else:
            # Try user:pass based Authentication
            username, password = None, None
            # see if we have HTTP-Basic Auth Data
            if self.request.headers.get('Authorization'):
                auth_type, encoded = self.request.headers.get('Authorization').split(None, 1)
                if auth_type.lower() == 'basic':
                    username, password = encoded.decode('base64').split(':', 1)

            # see if we have gotten some Form Data instead
            if not (username and password):
                username = self.request.get('username').strip()
                password = self.request.get('password').strip()

            # verify user & password
            if username:
                logging.info("Login Attempt for %s", username)
                credential = Credential.get_by_key_name(username)
                if credential and credential.secret == password:
                    # successfull login
                    session['uid'] = credential.uid
                    # redirect back where we came from
                    logging.info("Login durch %s/%s, Umleitung zu %s", username, self.request.remote_addr,
                                 continue_url)
                    self.redirect(continue_url)
                    return
                else:
                    logging.warning("Invalid Password %s:%s", username, password)

            # Render Template with Login form
            self.render({'continue': continue_url, 'domains': ALLOWED_DOMAINS}, 'login.html')


class LogoutHandler(OpenIdLoginHandler):
    def get(self):
        session = get_current_session()
        session['uid'] = None
        if session.is_active():
            session.terminate()
        # log out OpenID
        user = users.get_current_user()
        if user:
            self.redirect(users.create_logout_url("/logout"))
        else:
            # Render Template with logout confirmation
            self.render({}, 'logout.html')


def main():
    application = webapp2.WSGIApplication([
        ('logout', LogoutHandler),
        ('/logout', LogoutHandler),
        ('.*', OpenIdLoginHandler),
        ], debug=False)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
