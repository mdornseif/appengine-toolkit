#!/usr/bin/env python
# encoding: utf-8
"""gaetk/modelexporter.py Export db/ndb Tables / Models.

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
import time
import collections

from gaetk import compat
from gaetk2.datastore import query_iterator


def encode(val):
    u"""Encode value for exporter"""
    if isinstance(val, str):
        return val.decode('utf-8')
    if compat.xdb_iskey(val):
        return compat.xdb_id_or_name(val)
    return val


class ModelExporter(object):
    """Export all entities of a Model as XLS, CSV, etc."""

    def __init__(self, model,
                 query=None, uid=None, only=None, ignore=None, additional_fields=None, maxseconds=40):
        self.model = model
        self.uid = uid
        self.maxseconds = maxseconds
        if query is None:
            self.query = compat.xdb_queryset(model)
        else:
            self.query = query

        self.only = only
        self.ignore = ignore
        self.additional_fields = additional_fields

    @property
    def fields(self):
        """Liste der zu exportierenden Felder"""
        if not hasattr(self, '_fields'):
            fields = []
            props = compat.xdb_properties(self.model)
            for prop in props.values():
                name = compat.xdb_prop_name(prop)
                if self.only:
                    if name in self.only:
                        fields.append((compat.xdb_prop_creation_counter(prop), name))
                elif self.ignore:
                    if name not in self.ignore:
                        fields.append((compat.xdb_prop_creation_counter(prop), name))
                else:
                    fields.append((compat.xdb_prop_creation_counter(prop), name))

            if self.additional_fields:
                fields.extend((999, name) for name in self.additional_fields)

            self._fields = [name for (_, name) in sorted(fields)]

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

    def create_row(self, output, data, fixer=None):
        """Erzeugt eine einzelne Zeile im Output."""

        if not fixer:
            fixer = defaultfixer

        row = []
        for field in self.fields:
            attr = getattr(data, field)
            if callable(attr):
                tmp = attr()
            else:
                tmp = attr
            row.append(encode(tmp))
        if callable(data.key):
            row.append(unicode(data.key()))
        else:
            row.append(unicode(data.key.urlsafe()))
        output.writerow(fixer(row))

    def create_writer(self, fileobj):
        """Generiert den Ausgabedatenstrom aus fileobj."""
        return csv.writer(fileobj, dialect='excel', delimiter=b'\t')

    def to_csv(self, fileobj):
        """generate CSV in fileobj"""
        csvwriter = self.create_writer(fileobj)
        fixer = lambda row: [unicode(x).encode('utf-8') for x in row]
        self.create_header(csvwriter, fixer)
        start = time.time()
        for row in query_iterator(self.query):
            self.create_row(csvwriter, row, fixer)
            if time.time() - self.maxseconds > start:
                csvwriter.writerow(['truncated ...'])
                break

    def to_xls(self, fileobj):
        """generate XLS in fileobj"""
        import huTools.structured_xls
        xlswriter = huTools.structured_xls.XLSwriter()
        self.create_header(xlswriter)
        start = time.time()
        for row in query_iterator(self.query):
            self.create_row(xlswriter, row)
            if time.time() - self.maxseconds > start:
                xlswriter.writerow(['truncated ...'])
                break
        xlswriter.save(fileobj)


def defaultfixer(x):
    """Get rid of special data types."""
    if not isinstance(x, (basestring, float, int)):
        if isinstance(x, collections.Iterable):
            return ', '.join([str(y) for y in x])
        return unicode(x)
    return x
