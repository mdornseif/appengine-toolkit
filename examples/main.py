#!/usr/bin/env python
# encoding: utf-8
"""
main.py - central views for www.hudora.de

Created by Maximillian Dornseif on 2015-02-26
Copyright (c) 2015 HUDORA. All rights reserved.
"""

import config

import codecs
import datetime
import logging
import re

from google.appengine.api import memcache
from google.appengine.ext import ndb
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

    def create_jinja2env(self, extensions=()):
        """Erzeugt das jinja2 environment mit unseren Modifikationen."""
        # global _jinja_env_cache
        key = tuple(extensions)
        if key not in _jinja_env_cache:
            env = jinja2.Environment(loader=jinja2.FileSystemLoader(config.template_dirs),
                                     extensions=extensions,
                                     auto_reload=False,  # do check if the source changed
                                     trim_blocks=True,  # first newline after a block is removed
                                     bytecode_cache=jinja2.MemcachedBytecodeCache(memcache, timeout=600)
                                     )
            # Eigene Filter
            env.globals['bottommenuurl'] = \
                '/admin/'
            env.globals['bottommenuaddon'] = '<i class="fa fa-area-chart"></i> Admin'
            env.globals['huwawi_link'] = huwawi_link
            env.globals['profiler_includes'] = gae_mini_profiler.templatetags.profiler_includes
            _jinja_env_cache[key] = env
        return _jinja_env_cache[key]

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


class MarkdownFileHandler(wwwHandler):
    """Zeigt beliebige Markdown Files an."""
    template_name = 'gaetk_markdown.html'

    def get(self, path, *_args, **_kwargs):
        path = path.strip('/')
        path = re.sub(r'[^a-z/]', '', path)
        if not path:
            path = 'index'
        path = path + '.markdown'
        textfile = 'text/%s' % path

        try:
            with codecs.open(textfile, 'r', 'utf-8') as fileobj:
                text = fileobj.read()
                # wir gehen davon aus, dass die erste Zeile, die mit `# ` beginnt, der Titel ist
                for line in text.split('\n'):
                    if line.startswith('# '):
                        self.title = line.lstrip('# ')
                        break
            self.render({'text': text, 'title': self.title}, self.template_name)
        except IOError:
            raise gaetk.handler.HTTP404_NotFound("%s not available" % textfile)


class Warmup(wwwHandler):
    """Instanz initialisieren"""

    def authchecker(self, method, *args, **kwargs):
        """Authentifizierung abschalten."""
        pass

    def get(self):
        # _strptime importieren. hilft gegen
        # http://groups.google.com/group/google-appengine-python/browse_thread/thread/efbcffa181c32f33
        datetime.datetime.strptime('2000-01-01', '%Y-%m-%d').date()
        self.return_text('ok')


def make_app(url_mapping, debug=config.DEBUG):
    """Generate a WSGI-App"""
    app = ndb.toplevel(gaetk.webapp2.WSGIApplication(url_mapping, debug=debug))
    # hier werden wir auch das Error-Handling verankern. aber noch nicht ...
    # app.error_handlers[500] = ErrorHandler
    return app


application = make_app([
    (r'^/version\.txt$', gaetk.defaulthandlers.VersionHandler),
    (r'^/robots\.txt$', gaetk.defaulthandlers.RobotTxtHandler),
    (r'^/_ah/warmup$', Warmup),
    # (r'^/$', Homepage),
    (r'^(.*)$', MarkdownFileHandler),
], config.DEBUG)
