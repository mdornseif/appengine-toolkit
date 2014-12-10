#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/admin/options.py

Created by Christian Klein on 2011-08-22.
Copyright (c) 2011, 2014 HUDORA GmbH. All rights reserved.
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
from google.appengine.ext import ndb
from wtforms.ext.appengine.db import model_form

from gaetk.admin import util
from gaetk.admin.sites import site
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
    ordering = None

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

    # Wird dem Field beim Rendern übergeben
    # (ist das erste eigene Attribut)
    field_args = {}

    # Actions, bisher nicht implementiert.
    actions = []

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
        return order_field, '-' if direction == 'desc' else '+'

    def _get_queryset_db(self, ordering=None):
        """Queryset für Subklasse von db.Model"""
        query = self.model.all()
        if ordering:
            attr, direction = ordering
            if attr in self.model.properties():
                if direction == '-':
                    attr = '-' + attr
                query.order(attr)
        return query

    def _get_queryset_ndb(self, ordering):
        """Queryset für Subklasse von ndb.Model"""
        query = self.model.query()
        if ordering:
            attr, direction = ordering
            prop = self.model._properties.get(attr)
            if prop:
                if direction == '-':
                    return query.order(-prop)
                else:
                    return query.order(prop)
        return query

    def get_kind(self):
        kind = getattr(self.model, '_get_kind', None)
        if not kind:
            kind = getattr(self.model, 'kind')
        return kind()

    def get_queryset(self, request):
        """Gib das QuerySet für die Admin-Seite zurück

        Es wird die gewünschte Sortierung durchgeführt.
        """
        # TODO: Tupel: (attr, direction)
        ordering = self.get_ordering(request)
        if issubclass(self.model, ndb.Model):
            query = self._get_queryset_ndb(ordering)
        elif issubclass(self.model, db.Model):
            query = self._get_queryset_db(ordering)
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

    def get_object(self, encoded_key):
        """Ermittle die Instanz über den gegeben ID"""
        if issubclass(self.model, ndb.Model):
            key = ndb.Key(urlsafe=encoded_key)
            instance = key.get()
        elif issubclass(self.model, db.Model):
            instance = self.model.get(unquote(encoded_key))
        return instance

    def handle_blobstore_fields(self, handler, obj):
        """Upload für Blobs"""
        # Falls das Feld vom Typ cgi.FieldStorage ist, wurde eine Datei zum Upload übergeben
        for blob_upload_field in self.blob_upload_fields:
            blob = handler.request.params.get(blob_upload_field)
            if blob.__class__ == cgi.FieldStorage:
                blob_key = util.upload_to_blobstore(blob)
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
            if hasattr(obj, 'model') and issubclass(obj.model, db.Model):
                data = db.model_to_protobuf(obj).Encode()
                dblayer = 'db'
                key = obj.key()
            else:
                # assume ndb
                data = ndb.ModelAdapter().entity_to_pb(obj).Encode()
                dblayer = 'ndb'
                key = obj.key
            archived = DeletedObject(key_name=str(key), model_class=model_class.__name__,
                                     old_key=str(key), dblayer=dblayer, data=data)
            archived.put()
            # Indexierung für Admin-Volltextsuche
            from gaetk.admin.search import remove_from_index
            if dblayer == 'ndb':
                obj.key.delete()
                deferred.defer(remove_from_index, obj.key)
            else:
                obj.delete()
                deferred.defer(remove_from_index, obj.key())
            handler.add_message(
                'warning',
                u'<strong>%s</strong> wurde gelöscht. <a href="%s">Objekt wiederherstellen!</a>' % (
                    obj, archived.undelete_url()))
            raise gaetk.handler.HTTP302_Found(location='/admin/%s/%s/' % (
                util.get_app_name(model_class), util.get_kind(model_class)))

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
                from gaetk.admin.search import add_to_index
                deferred.defer(add_to_index, key)
                raise gaetk.handler.HTTP302_Found(location='/admin/%s/%s/' % (
                    util.get_app_name(model_class), util.get_kind(model_class)))
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
                # nettes feature, dsa fehlt: Methode `create` aufrufen.
                # Vorher: Im Code überprüfen, welche Modelle eine Methode `create` haben.
                if hasattr(self.model, 'create'):
                    factory = self.model.create
                else:
                    factory = self.model

                if issubclass(self.model, ndb.Model):
                    obj = factory(id=key_name, **form_data)
                else:
                    obj = factory(key_name=key_name, **form_data)

                self.handle_blobstore_fields(handler, obj)
                key = obj.put()
                handler.add_message('success', u'<strong>%s</strong> wurde angelegt.' % obj)
                # Indexierung für Admin-Volltextsuche
                from gaetk.admin.search import add_to_index
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
        exporter = ModelExporter(self.model)
        filename = '%s-%s.csv' % (self.get_kind(), datetime.datetime.now())
        handler.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        handler.response.headers['content-disposition'] = \
            'attachment; filename=%s' % filename
        exporter.to_csv(handler.response)

    def export_view_xls(self, handler, extra_context=None):  # pylint: disable=W0613
        """Request zum Exportieren von allen Objekten behandeln.

        `extra_context` ist für die Signatur erforderlich, wird aber nicht genutzt.
        """
        exporter = ModelExporter(self.model)
        filename = '%s-%s.xls' % (self.get_kind(), datetime.datetime.now())
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


import datetime
import csv


class ModelExporter(object):
    def __init__(self, model, query=None):
        self.model = model
        self.query = query

    @property
    def fields(self):
        """Liste der zu exportierenden Felder"""
        if not hasattr(self, '_fields'):
            fields = []
            # ndb & db compatibility
            props = getattr(self.model, '_properties', None)
            if not props:
                props = self.model.properties()
            for prop in props.values():
                # ndb & db compatibility
                fields.append(getattr(prop, '_name', getattr(prop, 'name', '?')))
            if hasattr(self, 'additional_fields'):
                fields.extend(self.additional_fields)
            fields.sort()
            self._fields = fields
        return self._fields

    def create_header(self, output, fixer=lambda x: x):
        """Erzeugt eine oder mehrere Headerzeilen in `output`"""
        output.writerow(fixer(['# Exported at:', str(datetime.datetime.now())]))
        output.writerow(fixer(self.fields + [u'Datenbankschlüssel']))

    def create_row(self, output, data, fixer=lambda x: x):
        """Erzeugt eine einzelne Zeile im Output."""
        row = []
        for field in self.fields:
            attr = getattr(data, field)
            if callable(attr):
                tmp = attr()
            else:
                tmp = attr
            row.append(unicode(tmp))
        if callable(data.key):
            row.append(unicode(data.key()))
        else:
            row.append(unicode(data.key.urlsafe()))
        output.writerow(fixer(row))

    def create_writer(self, fileobj):
        """Generiert den Ausgabedatenstrom aus fileobj."""
        return csv.writer(fileobj, dialect='excel', delimiter='\t')

    def to_csv(self, fileobj):
        csvwriter = csv.writer(fileobj, dialect='excel', delimiter='\t')
        fixer = lambda row: [unicode(x).encode('utf-8') for x in row]
        self.create_header(csvwriter, fixer)
        for row in self.model.query():
            self.create_row(csvwriter, row, fixer)

    def to_xls(self, fileobj):
        # we create a fake writer object to do buffering
        # because xlwt cant do streaming writes.

        xlswriter = XlsWriter()
        self.create_header(xlswriter)
        for row in self.model.query():
            self.create_row(xlswriter, row)
        xlswriter.save(fileobj)


class XlsWriter(object):
    def __init__(self):
        from xlwt import Workbook
        self.buff = []
        self.book = Workbook()
        self.sheet = self.book.add_sheet('Export')
        self.rownum = 0

    def writerow(self, row):
        col = 0
        for coldata in row:
            self.sheet.write(self.rownum, col, coldata)
            col += 1
        self.rownum += 1

    def save(self, fd):
        self.book.save(fd)
