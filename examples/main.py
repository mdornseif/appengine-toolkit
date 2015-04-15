#!/usr/bin/env python
# encoding: utf-8
"""
main.py - central views for www.hudora.de

Created by Maximillian Dornseif on 2015-02-26
Copyright (c) 2015 HUDORA. All rights reserved.
"""
import config

import logging

from google.appengine.api import memcache
import gae_mini_profiler.templatetags
import gaetk
import gaetk.defaulthandlers
import gaetk.handler
import jinja2
from jinja2.utils import Markup

# In-Process-Caching des Jinja2 Environment - das sollte threadsafe sein.
_jinja_env_cache = {}


@jinja2.contextfunction
def huwawi_link(context, data):
    """Link für ein beliebiges Objekt auf huWaWi erzeugen."""
    content = ''
    if context.get('is_admin') and data:
        content = '<a href="https://huwawi.hudora.de/spezial/suche/?q=%s">'
        content += '<i class="fa fa-cubes"></i></a>'
        content = content % data
    return Markup(content)


class wwwHandler(gaetk.handler.BasicHandler):
    """Handler für alle 'HTTP-Views' in wwwHudoraDe."""

    def __init__(self, *args, **kwargs):
        super(wwwHandler, self).__init__(*args, **kwargs)
        # Mailchimp ecommerce integration
        # Wenn die Kampagnen-ID (mc_cid) gesetzt ist,
        # wird sie zusammen mit der E-Mail-ID in die Session geschrieben
        if 'mc_cid' in self.request.GET:
            logging.info(u'EC360: %s/%s A', self.request.get('mc_cid'), self.request.get('mc_eid'))
            self.session['mc_cid'] = self.request.get('mc_cid')
            self.session['mc_eid'] = self.request.get('mc_eid')

    def add_jinja2env_globals(self, env):
        # Eigene Filter
        env.globals['bottommenuurl'] = '/admin/'
        env.globals['bottommenuaddon'] = '<i class="fa fa-area-chart"></i> Admin'
        env.globals['huwawi_link'] = huwawi_link
        env.globals['profiler_includes'] = gae_mini_profiler.templatetags.profiler_includes

    def default_template_vars(self, values):
        """Default variablen für Breadcrumbs etc."""
        # import snippets

        values = super(wwwHandler, self).default_template_vars(values)
        values.update(
            request=self.request,
            # show_snippet=snippets.show_snippet,
        )
        self.title = values.get('title')
        return values


class MarkdownFileHandler(wwwHandler, gaetk.handler.MarkdownFileHandler):
    """Markdown Files darstellen."""
    pass


def make_app(url_mapping, debug=config.DEBUG):
    """Generate a WSGI-App"""
    app = gaetk.webapp2.WSGIApplication(url_mapping, debug=debug)
    # hier werden wir auch das Error-Handling verankern. aber noch nicht ...
    # app.error_handlers[500] = ErrorHandler
    return app


application = make_app([
    (r'^/version\.txt$', gaetk.defaulthandlers.VersionHandler),
    (r'^/robots\.txt$', gaetk.defaulthandlers.RobotTxtHandler),
    (r'^/_ah/warmup$', gaetk.defaulthandlers.WarmupHandler),
    # (r'^/$', Homepage),
    (r'^(.*)$', MarkdownFileHandler),
], debug=config.DEBUG)
