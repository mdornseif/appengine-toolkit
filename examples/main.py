#!/usr/bin/env python
# encoding: utf-8
"""
main.py - example views

Created by Maximillian Dornseif on 2011-10-21.
Copyright (c) 2011, 2014 HUDORA. All rights reserved.
"""


import config

import gaetk.handler
import gaetk
import gaetk.defaulthandlers


class AuthenticatedHandler(gaetk.handler.BasicHandler):
    """Generic Handler forcing Authentication."""

    def authchecker(self, method, *args, **kwargs):
        """Force login for all pages"""
        self.login_required(True)



class Homepage(gaetk.handler.BasicHandler):
    """Startpage."""

    def get(self):
        """No parameters are accepted."""
        self.render(dict(title=u"HUDORA Express Startpage"), 'home.html')


class Authenticated(AuthenticatedHandler):
    """Startpage"""

    def get(self):
        """No parameters are accepted."""
        self.render(dict(
            title=u"authenticated Page",
            credential=self.credential
            ), 'authenticated.html')


# for the python 2.7 runrime application needs to be top-level
application = gaetk.webapp2.WSGIApplication([
        ('/authenticated/.*', Authenticated),
        ('/.*', Homepage),
        ('/version.txt', gaetk.defaulthandlers.VersionHandler),
        ('/robots.txt', gaetk.defaulthandlers.RobotTxtHandler),
    ], debug=True)
application.run()
