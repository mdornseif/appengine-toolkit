#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/admin/options.py

Created by Christian Klein on 2011-08-22.
Copyright (c) 2011, 2014 HUDORA GmbH. All rights reserved.
"""
import cgi
import collections
import datetime
import logging

import gaetk.handler
import wtforms

from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from wtforms_appengine.db import model_form

from gaetk import compat
from gaetk import modelexporter
from gaetk.admin import util
from gaetk.admin.models import DeletedObject
from gaetk.compat import xdb_kind


class AdminSite(object):
    """Konzept zur Verwaltung (per Weboberfläche) adminsitrierbarer GAE Models."""

    def __init__(self):
        """Konstruktor."""
        self._registry = {}

    def get_admin_class(self, key):
        return self._registry.get(key)

    def register(self, model_class, admin_class=None):
        """Registers the given model with the given admin class."""

        # We have some very nasty problems with cyclic imports
        # site registry depends on options and options depends
        # on a lot of stuff which depends on the site registry
        # if we would be able to break the dependency between the registry
        # AdminSite and ModelAdmin things would be much easier.
        if admin_class is None:
            admin_class = ModelAdmin

        # # Don't import the humongous validation code unless required
        # if admin_class and settings.DEBUG:
        #     from django.contrib.admin.validation import validate
        # else:
        #     validate = lambda model, adminclass: None

        if model_class in self._registry:
            logging.warn(u'The model %s is already registered', xdb_kind(model_class))

        # Instantiate the admin class to save in the registry
        self._registry[model_class] = admin_class(model_class, self)

    @property
    def registry(self):
        """Gib eine Kopie der Registry zurück"""
        return dict(self._registry)

    def get_model_class(self, application, model):
        """Klasse zu 'model' zurückgeben."""

        for model_class in self._registry:
            if model == xdb_kind(model_class) and application == util.get_app_name(model_class):
                return model_class


# The global AdminSite instance
site = AdminSite()


class ModelAdmin(object):
    """Admin Modell."""

    raw_id_fields = ()

    fields = None
    exclude = None

    # Mit 'order_field' laesst sich die Sortierung bei der Anzeige der Model-Instanzen
    # im Admin-Bereich anpassen. Als Default werden die Datensaetze in absteigender
    # Reihenfolge ihrer Erzeugung sortiert, jedoch kann jede Admin-Klasse die Sortierung
    # mit 'order_field' beeinflussen, indem sie ein bel. anderes Feld dort angibt.
    order_field = '-created_at'
    ordering = ''

    # Standardmaessig lassen wir die App Engine fuer das Model automatisch einen
    # Key generieren. Es besteht jedoch in der Admin-Klasse die Moeglichkeit, via
    # 'db_key_field=[propertyname]' ein Feld festzulegen, dessen Inhalt im Formular
    # als Key beim Erzeugen der Instanz genutzt wird.
    db_key_field = None

    prepopulated_fields = {}

    blob_upload_fields = []

    list_fields = ()
    list_display_links = ()
    list_per_page = 25

    post_create_hooks = []

    # Wird dem Field beim Rendern übergeben
    # (ist das erste eigene Attribut)
    field_args = {}

    read_only = False
    deletable = False

    # Actions, bisher nicht implementiert.
    actions = []

    def __init__(self, model, admin_site):
        self.model = model
        self.admin_site = admin_site

        if not self.list_fields:
            self.list_fields = compat.xdb_properties(self.model).keys()

        if not self.list_display_links:
            self.list_display_links = [self.list_fields[0]]

    def get_ordering(self, request):
        """Return the sort order attribute"""
        order_field = request.get('o')
        direction = request.get('ot', 'asc')

        if not order_field and self.ordering:
            if self.ordering.startswith('-'):
                direction = 'desc'
                order_field = self.ordering[1:]
            elif self.ordering.startswith('+'):
                direction = 'asc'
                order_field = self.ordering[1:]
            else:
                order_field = self.ordering
                direction = 'asc'

        if not order_field:
            return

        return order_field, '-' if direction == 'desc' else '+'

    def get_queryset(self, request):
        """Gib das QuerySet für die Admin-Seite zurück

        Es wird die gewünschte Sortierung durchgeführt.
        """
        ordering = self.get_ordering(request)
        return compat.xdb_queryset(self.model, ordering)

    def get_form(self, **kwargs):
        """Erzeuge Formularklasse für das Model"""

        # Erstmal nur das Form zurückgeben.
        # Soll sich doch jeder selbst um 'only' und 'exclude' kümmern,
        # bei model_form gehen aber leider alle Labels und Descriptions verloren.
        if hasattr(self, 'form'):
            return getattr(self, 'form')

        if self.exclude is None:
            exclude = []
        else:
            exclude = list(self.exclude)

        defaults = {
            'base_class': self.form,
            'only': self.fields,
            'exclude': (exclude + kwargs.get('exclude', [])) or None,
        }

        klass = model_form(self.model, **defaults)

        # label könnte man noch setzbar machen
        for blob_upload_field in self.blob_upload_fields:
            field = wtforms.FileField()
            setattr(klass, blob_upload_field, field)

        return klass

    def get_object(self, encoded_key):
        """Ermittle die Instanz über den gegeben ID"""
        return compat.xdb_get_instance(self.model, encoded_key)

    def handle_blobstore_fields(self, handler, obj, key_name):
        """Upload für Blobs"""
        # Falls das Feld vom Typ cgi.FieldStorage ist, wurde eine Datei zum Upload übergeben
        for blob_upload_field in self.blob_upload_fields:
            blob = handler.request.params.get(blob_upload_field)
            if blob.__class__ == cgi.FieldStorage:
                blob_key = util.upload_to_blobstore(obj, key_name, blob)
                setattr(obj, blob_upload_field, blob_key)

    def change_view(self, handler, object_id, extra_context=None):
        """View zum Bearbeiten eines vorhandenen Objekts"""

        obj = self.get_object(object_id)
        if obj is None:
            raise gaetk.handler.HTTP404_NotFound

        model_class = type(obj)
        form_class = self.get_form()

        if handler.request.get('delete') == 'yesiwant':
            # Der User hat gebeten, dieses Objekt zu löschen.
            key = compat.xdb_key(obj)
            data = compat.xdb_to_protobuf(obj)
            dblayer = 'ndb' if compat.xdb_is_ndb(obj) else 'db'
            archived = DeletedObject(key_name=str(key), model_class=model_class.__name__,
                                     old_key=str(key), dblayer=dblayer, data=data)
            archived.put()
            # Indexierung für Admin-Volltextsuche
            from gaetk.admin.search import remove_from_index
            if compat.xdb_is_ndb(obj):
                obj.key.delete()
                deferred.defer(remove_from_index, obj.key)
            else:
                obj.delete()
                deferred.defer(remove_from_index, obj.key())

            handler.add_message(
                'warning',
                u'<strong>{} {}</strong> wurde gelöscht. <a href="{}">Objekt wiederherstellen!</a>'.format(
                    compat.xdb_kind(self.model), compat.xdb_id_or_name(key), archived.undelete_url()))
            raise gaetk.handler.HTTP302_Found(location='/admin/%s/%s/' % (
                util.get_app_name(model_class), compat.xdb_kind(model_class)))

        # Wenn das Formular abgeschickt wurde und gültig ist,
        # speichere das veränderte Objekt und leite auf die Übersichtsseite um.
        if handler.request.method == 'POST':
            form = form_class(handler.request.POST)
            if form.validate():
                key_name = compat.xdb_id_or_name(compat.xdb_key(obj))
                self.handle_blobstore_fields(handler, obj, key_name)
                if hasattr(obj, 'update'):
                    obj.update(form.data)
                else:
                    form.populate_obj(obj)
                key = obj.put()
                handler.add_message(
                    'success',
                    u'<strong><a href="/admin/{}/{}/{}/">{} {}</a></strong> wurde gespeichert.'.format(
                        util.get_app_name(self.model),
                        compat.xdb_kind(self.model),
                        compat.xdb_str_key(key),
                        compat.xdb_kind(self.model),
                        compat.xdb_id_or_name(key)))

                # Indexierung für Admin-Volltextsuche
                from gaetk.admin.search import add_to_index
                deferred.defer(add_to_index, key)
                raise gaetk.handler.HTTP302_Found(location='/admin/%s/%s/' % (
                    util.get_app_name(model_class), compat.xdb_kind(model_class)))
        else:
            form = form_class(obj=obj)

        template_values = {'object': obj, 'form': form, 'field_args': self.field_args, 'admin_class': self}
        if extra_context is not None:
            template_values.update(extra_context)
        handler.render(template_values, self.get_template('change'))

    def add_view(self, handler, extra_context=None):
        """View zum Hinzufügen eines neuen Objekts"""
        form_class = self.get_form()

        # Standardmaessig lassen wir die App Engine fuer das Model automatisch einen
        # Key generieren. Es besteht jedoch in der Admin-Klasse die Moeglichkeit, via
        # 'db_key_field=[propertyname]' ein Feld festzulegen, dessen Inhalt im Formular
        # als Key beim Erzeugen der Instanz genutzt wird.
        admin_class = site.get_admin_class(self.model)
        key_field = None
        if admin_class and hasattr(admin_class, 'db_key_field'):
            key_field = admin_class.db_key_field

        # Wenn das Formular abgeschickt wurde und gültig ist,
        # speichere das veränderte Objekt und leite auf die Übersichtsseite um.
        if handler.request.method == 'POST':
            form = form_class(handler.request.POST)

            if form.validate():
                form_data = self._convert_property_data(form.data)
                key_name = form_data.get(key_field) if key_field else None

                # TODO: util.create_instance nutzen oder entfernen
                if hasattr(self.model, 'create'):
                    factory = self.model.create
                else:
                    factory = self.model

                if issubclass(self.model, ndb.Model):
                    obj = factory(id=key_name, **form_data)
                else:
                    obj = factory(key_name=key_name, **form_data)

                # Beim Anlegen muss dann halt einmal gespeichert werden,
                # ansonsten ist der ID unbekannt.
                if self.blob_upload_fields and key_name is None:
                    key_name = compat.xdb_id_or_name(obj.put())
                    self.handle_blobstore_fields(handler, obj, key_name)

                key = obj.put()
                handler.add_message(
                    'success',
                    u'<strong><a href="/admin/{}/{}/{}/">{} {}</a></strong> wurde angelegt.'.format(
                        util.get_app_name(self.model),
                        compat.xdb_kind(self.model),
                        compat.xdb_str_key(key),
                        compat.xdb_kind(self.model),
                        compat.xdb_id_or_name(key)))

                # Indexierung für Admin-Volltextsuche
                from gaetk.admin.search import add_to_index
                deferred.defer(add_to_index, key)

                # Call post-create-hooks
                if isinstance(self.post_create_hooks, collections.Iterable):
                    for hook in self.post_create_hooks:
                        deferred.defer(util.call_hook, hook, compat.xdb_str_key(key))

                raise gaetk.handler.HTTP302_Found(location='..')
        else:
            form = form_class()

        template_values = {'form': form, 'field_args': self.field_args, 'admin_class': self}
        if extra_context is not None:
            template_values.update(extra_context)
        handler.render(template_values, self.get_template('add'))

    def _convert_property_data(self, form_data):
        """Je nach Art der Model-Property muessen hier noch verschiedene Konvertierungen
           der rohen Eingaben aus dem Form durchgefuehrt werden, bevor sie ins Model geschrieben
           werden koennen."""
        # properties = self.model.properties()
        # for propname in form_data.keys():
        #     prop = properties.get(propname)

        #     bei StringListProperties muss die Eingabe der TextArea
        #     in eine Liste von Strings zerlegt werden
        #     if isinstance(prop, db.StringListProperty):
        #         form_data[propname] = form_data.get(propname, '').split('\n')

        return form_data

    def delete_view(self, handler, extra_context=None):  # pylint: disable=W0613
        """Request zum Löschen von (mehreren) Objekten behandeln.

        Redirectet bei Erfolg zur Objektliste.
        `extra_context` ist für die Signatur erforderlich, wird aber nicht genutzt.
        """
        if handler.request.method != 'POST':
            raise gaetk.handler.HTTP400_BadRequest(u'Falsche Request Methode für diesen Aufruf: %s' %
                                                   handler.request.method)
        # Instanzen sammeln und dann gemeinsam löschen
        keys = []
        for object_id in handler.request.get_all('object_id'):
            obj = self.get_object(object_id)
            if obj is None:
                raise gaetk.handler.HTTP404_NotFound(u'Keine Instanz zu ID %s gefunden.' % object_id)
            logging.info(u'Delete %s', object_id)
            if issubclass(self.model, ndb.Model):
                keys.append(ndb.Key(urlsafe=object_id))
            elif issubclass(self.model, db.Model):
                keys.append(db.Key(object_id))

        if issubclass(self.model, ndb.Model):
            ndb.delete_multi(keys)
        elif issubclass(self.model, db.Model):
            db.delete(keys)

        raise gaetk.handler.HTTP302_Found(location='..')

    def export_view_csv(self, handler, extra_context=None):  # pylint: disable=W0613
        """Request zum Exportieren von allen Objekten behandeln.

        `extra_context` ist für die Signatur erforderlich, wird aber nicht genutzt.
        """
        # irgendwann werden wir hier einen longtask nutzen muessen
        exporter = modelexporter.ModelExporter(self.model)
        filename = '%s-%s.csv' % (compat.xdb_kind(self.model), datetime.datetime.now())
        handler.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        handler.response.headers['content-disposition'] = \
            'attachment; filename=%s' % filename
        exporter.to_csv(handler.response)

    def export_view_xls(self, handler, extra_context=None):  # pylint: disable=W0613
        """Request zum Exportieren von allen Objekten behandeln.

        `extra_context` ist für die Signatur erforderlich, wird aber nicht genutzt.
        """
        exporter = modelexporter.ModelExporter(self.model)
        filename = '%s-%s.xls' % (compat.xdb_kind(self.model), datetime.datetime.now())
        handler.response.headers['Content-Type'] = 'application/msexcel'
        handler.response.headers['content-disposition'] = \
            'attachment; filename=%s' % filename
        exporter.to_xls(handler.response)

    def get_template(self, action):
        """Auswahl des zur `action` passenden templates."""

        # In Jinja2 kann man doch auch eine Liste mit Template-Pfaden zurückgeben.
        # Das wäre hier doch genau das richtige!

        if action == 'delete':
            pass

        attr = action + '_form_template'
        return getattr(self, attr, 'admin/detail.html')
