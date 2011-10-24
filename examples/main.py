#!/usr/bin/env python
# encoding: utf-8
"""
p_views.py

Created by Maximillian Dornseif on 2011-10-21.
Copyright (c) 2011 HUDORA. All rights reserved.
"""


import config

logging.info(sys.path)
import gaetk.handler
import gaetk
import gaetk.defaulthandlers


class Homepage(gaetk.handler.BasicHandler):
    """Strt/Übersichtsseite"""

    def get(self):
        """No parameters are accepted."""
        self.render(dict(title=u"huWaWi Startseite"), 'planet_home.html')


# for the python 2.7 runrime application needs to be top-level
application = gaetk.webapp2.WSGIApplication([
        ('/planet/', Homepage),
        ('/version.txt', gaetk.defaulthandlers.VersionHandler),
        ('/robots.txt', gaetk.defaulthandlers.RobotTxtHandler),
    ], debug=True)
application.run()
