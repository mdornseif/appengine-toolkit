#!/usr/bin/env python
# encoding: utf-8
"""
common/admin/options.py

Created by Christian Klein on 2011-08-22.
Copyright (c) 2011 HUDORA GmbH. All rights reserved.
"""
import config
config.imported = True

import cgi
import logging
from urllib import unquote

import gaetk.handler
import wtforms

from google.appengine.ext import db
from google.appengine.ext import deferred
from wtforms.ext.appengine.db import model_form

from gaetk.admin.models import DeletedObject


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

    # Standardmaessig lassen wir die App Engine fuer das Model automatisch einen
    # Key generieren. Es besteht jedoch in der Admin-Klasse die Moeglichkeit, via
    # 'db_key_field=[propertyname]' ein Feld festzulegen, dessen Inhalt im Formular
    # als Key beim Erzeugen der Instanz genutzt wird.
    db_key_field = None

    prepopulated_fields = {}

    blob_upload_fields = []
    list_fields = ('__str__',)
    list_display_links = ()
    list_per_page = 25
    ordering = None

    # Wird dem Field beim Rendern übergeben
    # (ist das erste eigene Attribut)
    field_args = {}

    # Actions
    actions = []  # wohl eher nicht... Also entfernen!

    def __init__(self, model, admin_site):
        self.model = model
        self.admin_site = admin_site

        if not self.list_display_links:
            self.list_display_links = [self.list_fields[0]]

    def get_ordering(self, request):
        """Return the sort order attribute"""
        order_field = request.get('o')

        if not order_field:  # in self.model
            order_field = self.ordering
        if not order_field:
            return

        direction = request.get('ot', 'asc')
        if direction == 'desc':
            order_field = '-' + order_field
        return order_field

    def get_queryset(self, request):
        """Gib das QuerySet für die Admin-Seite zurück

        Es wird die gewünschte Sortierung durchgeführt.
        """
        query = self.model.all()
        ordering = self.get_ordering(request)
        if ordering:
            query.order(ordering)
        return query

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
            'base_class': self.form,  # pylint: disable=E1101
            'only': self.fields,
            'exclude': (exclude + kwargs.get('exclude', [])) or None,
        }

        klass = model_form(self.model, **defaults)

        # label könnte man noch setzbar machen
        for blob_upload_field in self.blob_upload_fields:
            field = wtforms.FileField()
            setattr(klass, blob_upload_field, field)

        return klass

    def get_object(self, key):
        """Ermittle die Instanz über den gegeben ID"""
        return self.model.get(unquote(key))
    # logs...

    def handle_blobstore_fields(self, handler, obj):
        """Upload für Blobs"""
        from common.admin.util import upload_to_blobstore

        # Falls das Feld vom Typ cgi.FieldStorage ist, wurde eine Datei zum Upload übergeben
        for blob_upload_field in self.blob_upload_fields:
            blob = handler.request.params.get(blob_upload_field)
            if blob.__class__ == cgi.FieldStorage:
                blob_key = upload_to_blobstore(blob)
                setattr(obj, blob_upload_field, blob_key)

    def change_view(self, handler, object_id, extra_context=None):
        """View zum Bearbeiten eines vorhandenen Objekts"""

        from common.admin.util import get_app_name

        obj = self.get_object(object_id)
        if obj is None:
            raise gaetk.handler.HTTP404_NotFound

        model_class = type(obj)
        form_class = self.get_form()

        if handler.request.get('delete') == 'yesiwant':
            # Der User hat gebeten, dieses Objekt zu löschen.
            data = db.model_to_protobuf(obj).Encode()
            archived = DeletedObject(key_name=str(obj.key()), model_class=model_class.__name__,
                                     old_key=str(obj.key()), data=data)
            archived.put()
            obj.delete()
            # Indexierung für Admin-Volltextsuche
            from common.admin.search import remove_from_index
            deferred.defer(remove_from_index, obj.key())
            handler.add_message(
                'warning',
                u'<strong>%s</strong> wurde gelöscht. <a href="%s">Objekt wiederherstellen!</a>' % (
                    obj, archived.undelete_url()))
            raise gaetk.handler.HTTP302_Found(location='/admin/%s/%s/' % (get_app_name(model_class),
                                                                          model_class.kind()))

        # Wenn das Formular abgeschickt wurde und gültig ist,
        # speichere das veränderte Objekt und leite auf die Übersichtsseite um.
        if handler.request.method == 'POST':
            form = form_class(handler.request.POST)
            if form.validate():
                self.handle_blobstore_fields(handler, obj)
                if hasattr(obj, 'update'):
                    obj.update(form.data)
                else:
                    form.populate_obj(obj)
                key = obj.put()
                handler.add_message('success', u'<strong>%s</strong> wurde gespeichert.' % obj)
                # Indexierung für Admin-Volltextsuche
                from common.admin.search import add_to_index
                deferred.defer(add_to_index, key)
                raise gaetk.handler.HTTP302_Found(location='/admin/%s/%s/' % (
                    get_app_name(model_class), model_class.kind()))
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
        from common.admin.sites import site
        admin_class = site._registry.get(self.model)
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
                # nettes feature, dsa fehlt: Methode `create` aufrufen.
                # Vorher: Im Code überprüfen, welche Modelle eine Methode `create` haben.
                if hasattr(self.model, 'create'):
                    factory = self.model.create
                else:
                    factory = self.model
                obj = factory(key_name=key_name, **form_data)
                self.handle_blobstore_fields(handler, obj)
                key = obj.put()
                handler.add_message('success', u'<strong>%s</strong> wurde angelegt.' % obj)
                # Indexierung für Admin-Volltextsuche
                from common.admin.search import add_to_index
                deferred.defer(add_to_index, key)
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
        objects = []
        for object_id in handler.request.get_all('object_id'):
            obj = self.get_object(object_id)
            if obj is None:
                raise gaetk.handler.HTTP404_NotFound(u'Keine Instanz zu ID %s gefunden.' % object_id)
            objects.append(obj)
            logging.info(u'Delete %s', object_id)
        db.delete(objects)
        raise gaetk.handler.HTTP302_Found(location='..')

    def get_template(self, action):
        """Auswahl des zur `action` passenden templates."""

        # In Jinja2 kann man doch auch eine Liste mit Template-Pfaden zurückgeben.
        # Das wäre hier doch genau das richtige!

        if action == 'delete':
            pass

        attr = action + '_form_template'
        return getattr(self, attr, 'admin/detail.html')
