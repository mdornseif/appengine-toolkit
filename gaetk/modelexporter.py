#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/modelexporter.py Export db/ndb Tables / Models

Created by Maximillian on 2014-12-10.
Copyright (c) 2014-2016 HUDORA GmbH. All rights reserved.

Usage:

    exporter = ModelExporter(ic_AuftragsPosition)
    filename = '%s-%s.xls' % (compat.xdb_kind(ic_AuftragsPosition), datetime.datetime.now())
    handler.response.headers['Content-Type'] = 'application/msexcel'
    handler.response.headers['content-disposition'] = \
        'attachment; filename=%s' % filename
    exporter.to_xls(handler.response)
    # exporter.to_csv(handler.response)
"""
import csv
import datetime

from gaetk import compat
from gaetk.infrastructure import query_iterator


class ModelExporter(object):
    """Export all entities of a Model as XLS, CSV, etc."""

    def __init__(self, model, query=None, uid=None):
        self.model = model
        self.uid = uid
        if query is None:
            self.query = compat.xdb_queryset(model)
        else:
            self.query = query

    @property
    def fields(self):
        """Liste der zu exportierenden Felder"""
        if not hasattr(self, '_fields'):
            fields = []
            props = compat.xdb_properties(self.model)
            for prop in props.values():
                # ndb & db compatatibility
                name = getattr(prop, '_name', getattr(prop, 'name', '?'))
                if name not in getattr(self, 'unwanted_fields', []):
                    fields.append(name)
            if hasattr(self, 'additional_fields'):
                fields.extend(self.additional_fields)
            fields.sort()
            self._fields = fields
        return self._fields

    def create_header(self, output, fixer=lambda x: x):
        """Erzeugt eine oder mehrere Headerzeilen in `output`"""
        if self.uid:
            output.writerow(fixer([
                '# Exported at:',
                str(datetime.datetime.now()),
                'for',
                self.uid]))
        else:
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
        """generate CSV in fileobj"""
        csvwriter = csv.writer(fileobj, dialect='excel', delimiter='\t')
        fixer = lambda row: [unicode(x).encode('utf-8') for x in row]
        self.create_header(csvwriter, fixer)
        for row in query_iterator(self.query):
            self.create_row(csvwriter, row, fixer)

    def to_xls(self, fileobj):
        """generate XLS in fileobj"""
        import huTools.structured_xls
        xlswriter = huTools.structured_xls.XLSwriter()
        self.create_header(xlswriter)
        for row in query_iterator(self.query):
            self.create_row(xlswriter, row)
        xlswriter.save(fileobj)
