#!/usr/bin/env python
# encoding: utf-8
"""
admin/views.py - administrationsinterface - inspieriert von Django.

Created by Christian Klein on 2011-08-10.
Copyright (c) 2011, 2013, 2014 HUDORA GmbH. All rights reserved.
"""
import config

import datetime
import gaetk.handler
import webapp2
from google.appengine.datastore import entity_pb
from google.appengine.ext import db, ndb

from gaetk.admin import autodiscover
from gaetk.admin import search
from gaetk.admin.models import DeletedObject
from gaetk.admin.sites import site
from gaetk.admin.util import get_app_name
from gaetk.compat import xdb_kind


def make_app(url_mapping):
    """
    Factory für WSGI-Application

    Erzeugt WSGI-App und setzt Fehlerhandler.
    """
    application = webapp2.WSGIApplication(url_mapping, debug=getattr(config, 'DEBUG', False))
    # application.error_handlers[404] = handle_404
    # application.error_handlers[500] = handle_500
    return application


class AdminHandler(gaetk.handler.BasicHandler):
    """Basisklasse AdminHandler."""
    def authchecker(self, method, *args, **kwargs):
        """Autentifizierung. `login: required` in app.yaml macht die Drecksarbeit für uns."""

        self.login_required()
        if not self.is_admin():
            raise gaetk.handler.HTTP403_Forbidden

    def default_template_vars(self, values):
        """Default variablen für Breadcrumbs etc."""
        values = super(AdminHandler, self).default_template_vars(values)
        values.update(dict(
            request=self.request,
            now=datetime.datetime.now(),
            kw=datetime.date.today().isocalendar()[1]),
            permissions=[],
            is_admin=self.is_admin())
        if self.credential:
            values.update(dict(permissions=self.credential.permissions))
        self.title = values.get('title')
        return values


class AdminIndexHandler(AdminHandler):
    """Übersichtsseite aller registrierter Models sortiert nach Applikationen"""

    def get(self):
        """Zeige Template mit allen registrierten Models an"""

        apps = {}
        for model_class in site.registry.keys():
            application = get_app_name(model_class)
            apps.setdefault(application, []).append(xdb_kind(model_class))
        self.render({'apps': apps}, 'admin/index.html')


class AdminListHandler(AdminHandler):
    """Übersichtsseite eines Models mit Liste aller Entities"""

    def get(self, application, model):
        """Rendert eine Liste aller registrierten Modells."""

        model_class = site.get_model_class(application, model)
        if not model_class:
            raise gaetk.handler.HTTP404_NotFound('No model %s' % ('%s.%s' % (application, model)))
        admin_class = site.get_admin_class(model_class)

        # unsupported: Link-Fields (oder wie das heißt)
        # unsupported: callables in List_fields
        query = admin_class.get_queryset(self.request)

        template_values = self.paginate(query,
                                        defaultcount=admin_class.list_per_page,
                                        datanodename='object_list', calctotal=False)
        template_values['list_fields'] = admin_class.list_fields
        template_values['app'] = application
        template_values['model'] = model
        template_values['model_class'] = model_class
        self.render(template_values, 'admin/list.html')


class AdminSearchHandler(AdminHandler):
    """Suche im Volltextsuchindex des Administrationsinterfaces"""

    def get(self, application, model):
        """Erwartet den Parameter `q`"""

        model_class = site.get_model_class(application, model)
        if not model_class:
            raise gaetk.handler.HTTP404_NotFound('No model %s' % ('%s.%s' % (application, model)))

        pagesize = 40
        term = self.request.get('q')

        limit = self.request.get_range('limit', default=40, min_value=10)
        offset = self.request.get_range('offset', default=0, min_value=0)
        hits, total = search.fsearch(term, model, limit=limit, offset=offset)

        self.render(dict(app=application,
                         model=model,
                         model_class=model_class,
                         hits=hits,
                         total=total,
                         term=term,
                         page=offset // pagesize,
                         pagesize=pagesize),
                    'admin/search.html')


class AdminDetailHandler(AdminHandler):
    """Detailseite zu einer Entity"""

    def dispatch(self):
        """Handler, der die richtige Methode für die Aktion aufruft"""

        args = self.request.route_args
        application, model, action_or_objectid = args

        # Authchecker, hat der User Zugriff auf das Model mit der Action wäre noch was.

        model_class = site.get_model_class(application, model)
        if not model_class:
            raise gaetk.handler.HTTP404_NotFound('No model %s' % ('%s.%s' % (application, model)))
        admin_class = site.get_admin_class(model_class)

        import logging
        logging.info("%s %s", action_or_objectid, self.request.route_args)
        # Bestimme Route! Da könnte man dann auch einen Handler mit angeben.
        if action_or_objectid == 'add':
            admin_class.add_view(self)
        elif action_or_objectid == 'export_xls':
            admin_class.export_view_xls(self)
        elif action_or_objectid == 'export_csv':
            admin_class.export_view_csv(self)
        elif action_or_objectid == 'delete':
            admin_class.delete_view(self)
        else:
            admin_class.change_view(self, action_or_objectid,
                                    extra_context=dict(app=application, model=model))


class AdminUndeleteHandler(AdminHandler):
    """Daten, die gelöscht wurden, wieder herstellen."""
    def get(self, key):
        """Objekt mit <key> wiederherstellen."""
        archived = DeletedObject.get(key)
        if archived.dblayer == 'ndb':
            entity = ndb.ModelAdapter().pb_to_entity(entity_pb.EntityProto(archived.data))
        else:
            # precondition: model class must be imported
            entity = db.model_from_protobuf(entity_pb.EntityProto(archived.data))
        entity.put()
        archived.delete()
        self.add_message(
            'success',
            u'Objekt <strong><A href="/admin/%s/%s/%s/">%s</a></strong> wurde wieder hergestellt.' % (
                get_app_name(entity.__class__), entity.__class__.__name__, entity.key(), entity))
        raise gaetk.handler.HTTP301_Moved(location='/admin/%s/%s/' % (
            get_app_name(entity.__class__), entity.__class__.__name__))


autodiscover()
import gaetk.snippets
app = make_app([(r'^/admin/_undelete/(.+)', AdminUndeleteHandler),
                (r'^/admin/snippet/edit/', gaetk.snippets.SnippetEditHandler),
                (r'^/admin/(\w+)/(\w+)/search/$', AdminSearchHandler),
                (r'^/admin/(\w+)/(\w+)/(.+?)/', AdminDetailHandler),
                (r'^/admin/(\w+)/(\w+)/$', AdminListHandler),
                (r'^/admin/?$', AdminIndexHandler),
                ])
