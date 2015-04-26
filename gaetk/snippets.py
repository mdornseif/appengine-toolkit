#!/usr/bin/env python
# encoding: utf-8
"""
snippets.py - editable parts of webpages

Created by Maximillian Dornseif on 2014-11-22.
Copyright (c) 2014 HUDORA. All rights reserved.
"""

import cgi
import logging
import os
import random
import traceback

import gaetk
import gaetk.defaulthandlers
import gaetk.handler
import gaetk.tools
import huTools.http.tools
import huTools.markdown2
import jinja2

from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import memcache


class gaetk_Snippet(ndb.Model):
    """Encodes a small pice of text for a jinja2 template."""
    name = ndb.StringProperty()
    markdown = ndb.TextProperty()
    path_info = ndb.StringProperty()
    updated_at = ndb.DateTimeProperty(auto_now=True)
    created_at = ndb.DateTimeProperty(auto_now_add=True)


@jinja2.environmentfunction
def show_snippet(env, name, default=''):
    """Render a snippet inside a jinja2 template."""
    name = gaetk.tools.slugify(name.replace(' ', ''))
    snippet = gaetk_Snippet.get_by_id(name)
    if not snippet:
        snippet = gaetk_Snippet(id=name, name=name, markdown=default)
        snippet.put()
    path_info = os.environ.get('PATH_INFO', '?')
    if snippet.path_info is None or not path_info.startswith(snippet.path_info.encode('utf-8', 'ignore')):
        if not snippet.path_info or random.random() < 0.01:
            snippet.path_info = path_info
            snippet.put()

    edit = ''
    if users.is_current_user_admin():
        edit = u'''<div style="float:right"><a
href="/admin/snippet/edit/?id={0}#edit" class="snippet_edit_button"
id="snippet_{1}_button"><i class="fa fa-pencil-square-o"></i></a></div>
<script>
$( "#snippet_{1}_button" ).mouseover(function() {{
$( this ).parents(".snippetenvelope").effect( "highlight")
}}); </script>
'''.format(name, huTools.http.tools.quote(name))

    content = memcache.get('gaetk_snippet2:%s:rendered' % name)
    if content is None:
        template = env.from_string(huTools.markdown2.markdown(snippet.markdown))
        try:
            content = template.render({})
            if not memcache.set('gaetk_snippet2:%s:rendered' % name, content, 600):
                logging.error('Memcache set failed.')
        except Exception, msg:
            logging.error("%s", msg)
            traceback.print_exc()
            return '''<!-- Rendering error: %s -->%s''' % (cgi.escape(str(msg)), edit)

    return jinja2.Markup(u'''<div class="snippetenvelope"
id="snippet_{0}_envelop">{1}<div class="snippet"
id="snippet_{0}">{2}</div></div>'''.format(name, edit, content))


class SnippetEditHandler(gaetk.handler.BasicHandler):
    """Allow a admin-user to change a snippet."""

    def get(self):
        self.login_required()
        if not self.is_admin():
            raise gaetk.handler.HTTP403_Forbidden("Access denied!")
        name = self.request.get('id')
        snippet = gaetk_Snippet.get_by_id(id=name)
        self.render(
            dict(title=u"Edit %s" % name, snippet=snippet),
            'gaetk_snippet_edit.html')

    def post(self):
        name = self.request.get("name")
        markdown = self.request.get("sniptext")
        snippet = gaetk_Snippet.get_by_id(id=name)
        snippet.markdown = markdown
        snippet.put()
        memcache.delete('gaetk_snippet:%s:rendered' % name)
        raise gaetk.handler.HTTP303_SeeOther(location=snippet.path_info)
