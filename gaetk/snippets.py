#!/usr/bin/env python
# encoding: utf-8
"""
snippets.py - editable parts of webpages

Created by Maximillian Dornseif on 2014-11-22.
Copyright (c) 2014, 2017 HUDORA. All rights reserved.
"""

import cgi
import logging
import os
import random

import jinja2

import gaetk
import gaetk.defaulthandlers
import gaetk.handler
import gaetk.jinja_filters
import gaetk.tools
import huTools.http.tools

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import ndb


class gaetk_Snippet(ndb.Model):
    """Encodes a small pice of text for a jinja2 template."""
    name = ndb.StringProperty()
    markdown = ndb.TextProperty()
    path_info = ndb.StringProperty(default='')
    updated_at = ndb.DateTimeProperty(auto_now=True)
    created_at = ndb.DateTimeProperty(auto_now_add=True)


@jinja2.environmentfunction
def show_snippet(env, name, default=''):
    """Render a snippet inside a jinja2 template."""
    db_name = gaetk.tools.slugify(name.replace(' ', ''))
    url_name = huTools.http.tools.quote(db_name)
    css_name = gaetk.jinja_filters.filter_cssencode(db_name)
    path_info = os.environ.get('PATH_INFO', '?')

    # display edit-button to admin users
    edit = u''
    if users.is_current_user_admin():
        edit = u'''<div
            id="{css_name}"
            style="float:right"
        ><a
            href="/admin/snippet/edit/?id={url_name}#edit&continue_url={path_info}#{css_name}"
            class="snippet_edit_button"
            id="snippet_{css_name}_button"
        ><i
            class="fa fa-pencil-square-o">
        </i></a></div>
        <script>
            $("#snippet_{css_name}_button").mouseover(function() {{
                $(this).parents(".snippetenvelope").effect("highlight")
            }})
        </script>
    '''.format(name=name, css_name=css_name, url_name=url_name, path_info=path_info)

    content = memcache.get('gaetk_snippet2:%s:rendered' % db_name)
    if random.random() < 0.01 or content is None:
        snippet = gaetk_Snippet.get_by_id(db_name)
        if not snippet:
            logging.info("generating snippet %s", db_name)
            snippet = gaetk_Snippet(id=db_name, name=db_name, markdown=default)

        if snippet.path_info is None or not path_info.startswith(snippet.path_info.encode('utf-8', 'ignore')):
            # with 1% chance we overwrite the existing path
            if not snippet.path_info or random.random() < 0.01:
                snippet.path_info = path_info
                snippet.put()

        # generate snippet
        if content is None:
            try:
                content = render(name, env, snippet.markdown)
            except Exception as exception:
                # TODO: raise in raven
                logging.exception(u'Fehler beim Rendern des Snippet %s: %s', snippet.key.id(), exception)
                return '<!-- Rendering error: %s -->%s' % (cgi.escape(str(exception)), edit)

    assert content is not None
    return jinja2.Markup(u'''<div
            class="snippetenvelope"
            id="snippet_{css_name}_envelop"
            data-snippet="{name}"
        >{edit}<div
            class="snippet" id="snippet_{css_name}">{content}
        </div></div>'''.format(
            css_name=css_name, name=name, edit=edit, content=content))


def render(name, env, markdown):
    """Snippet mit Jinja2 rendern und in memcache speichern"""
    import huTools.markdown2
    template = env.from_string(huTools.markdown2.markdown(markdown))
    content = template.render({})
    if not memcache.set('gaetk_snippet2:%s:rendered' % name, content, 600):
        logging.error('Memcache set failed.')
    return content


class SnippetEditHandler(gaetk.handler.BasicHandler):
    """Allow a admin-user to change a snippet."""

    def authchecker(self, *args, **kwargs):
        """Only admin-users may edit a snippet"""
        self.login_required()
        if not self.is_admin():
            raise gaetk.handler.HTTP403_Forbidden("Access denied!")

    def get(self):
        name = self.request.get('id')
        if not name:
            raise gaetk.handler.HTTP404_NotFound
        snippet = gaetk_Snippet.get_by_id(id=name)
        continue_url = self.request.get('continue_url', '')
        self.render(
            dict(title=u"Edit %s" % name, name=name, snippet=snippet, continue_url=continue_url),
            'gaetk_snippet_edit.html')

    def post(self):
        name = self.request.get('name')
        markdown = self.request.get('sniptext', u'')
        continue_url = self.request.get('continue_url', '')
        try:
            render(name, self.create_jinja2env(), markdown)
        except Exception as exception:
            logging.exception(u'Fehler beim Rendern des Snippet: %s', exception)
            self.add_message('error', u'Fehler: %s' % exception)
            raise gaetk.handler.HTTP303_SeeOther(location=self.request.referer)

        snippet = gaetk_Snippet.get_or_insert(name, name=name, path_info='')
        snippet.markdown = markdown
        snippet.put()

        if continue_url:
            location = continue_url
        elif snippet.path_info:
            location = snippet.path_info
        else:
            location = '/admin/'
        raise gaetk.handler.HTTP303_SeeOther(location=location)
