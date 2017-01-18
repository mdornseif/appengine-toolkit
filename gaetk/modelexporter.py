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
import time
import logging

from gaetk import compat
from gaetk.infrastructure import query_iterator


class ModelExporter(object):
    """Export all entities of a Model as XLS, CSV, etc."""

    def __init__(self, model,
                 query=None,
                 uid=None,
                 only=None,
                 ignore=None,
                 additional_fields=None,
                 field_mapping=None,
                 sort_order=None,
                 grouping=None,
                 maxseconds=40):
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
        self.field_mapping = field_mapping
        self.sort_order = sort_order
        self.grouping = grouping

    def get_sort_key(self, prop, name):
        if self.sort_order:
            if name in self.sort_order:
                return self.sort_order.index(name)
            else:
                return 998
        return compat.xdb_prop_creation_counter(prop)

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
                        fields.append((self.get_sort_key(prop, name), name))
                elif self.ignore:
                    if name not in self.only:
                        fields.append((self.get_sort_key(prop, name), name))
                else:
                    fields.append((self.get_sort_key(prop, name), name))

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

        if self.field_mapping:
            row = [self.field_mapping.get(col, col) for col in self.fields]
        else:
            row = self.fields

        if self.ignore and not '_key' in self.ignore:
            row.append(u'Datenbankschlüssel')

        output.writerow(fixer(row))

    def create_row(self, output, obj, fixer=lambda x: x):
        """Erzeugt eine einzelne Zeile im Output."""

        row = []
        for field in self.fields:
            attr = getattr(obj, field)
            if callable(attr):
                tmp = attr()
            else:
                tmp = attr
            row.append(unicode(tmp))

        if self.ignore and not '_key' in self.ignore:
            row.append(unicode(compat.xdb_str_key(compat.xdb_key(obj.key))))

        output.writerow(fixer(row))

    def create_rows(self, output, fixer=lambda x: x):
        """Create rows..."""

        start = time.time()
        current_group = None
        for obj in query_iterator(self.query):
            if self.grouping:
                next_group = getattr(obj, self.grouping, u'')
                if current_group and current_group != next_group:
                    output.writerow([next_group])
                current_group = next_group

            self.create_row(output, obj, fixer)
            if time.time() - self.maxseconds > start:
                csvwriter.writerow(['truncated ...'])
                break

    def to_csv(self, fileobj):
        """Generate CSV in fileobj"""

        csvwriter = csv.writer(fileobj, dialect='excel', delimiter='\t')
        fixer = lambda row: [unicode(x).encode('utf-8') for x in row]
        self.create_header(csvwriter, fixer)
        self.create_rows(csvwriter, fixer)

    def to_xls(self, fileobj):
        """Generate XLS in fileobj"""

        import huTools.structured_xls
        xlswriter = huTools.structured_xls.XLSwriter()
        self.create_header(xlswriter)
        self.create_rows(xlswriter)
        xlswriter.save(fileobj)
