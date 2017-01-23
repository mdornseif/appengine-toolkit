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

    def get_sort_key(self, prop, name):
        """
        Sortierreihenfolge für Ausgabe in Tabelle (CSV, XLS)

        Wurden nur bestimmte Felder zum Export ausgewählt (Parameter `only`),
        wird die Reihenfolge der Felder aus Sortierreihenfolge verwendet.
        Ansonsten wird die Reihenfolge verwendet, in der die Model-Attribute
        definiert wurden.
        """

        if self.only:
            if name in self.only:
                return self.only.index(name)
            else:
                return 998
        else:
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

    def create_header(self, output, config, fixer=lambda x: x):
        """Erzeugt eine oder mehrere Headerzeilen in `output`"""
        if self.uid:
            output.writerow(fixer([
                '# Exported at:',
                str(datetime.datetime.now()),
                'for',
                self.uid]))
        else:
            output.writerow(fixer(['# Exported at:', str(datetime.datetime.now())]))

        if 'field_mapping' in config:
            row = [config['field_mapping'].get(col, col) for col in self.fields]
        else:
            row = self.fields

        if config['export_key']:
            row.append(u'Datenbankschlüssel')

        output.writerow(fixer(row))

    def create_row(self, obj):
        """Erzeugt eine einzelne Zeile im Output."""

        row = []
        for field in self.fields:
            attr = getattr(obj, field)
            if callable(attr):
                tmp = attr()
            else:
                tmp = attr
            row.append(unicode(tmp))

        if config['export_key']:
            row.append(unicode(compat.xdb_str_key(compat.xdb_key(obj.key))))

        return row

    def create_rows(self, output, config, fixer=lambda x: x):
        """Create rows..."""

        start = time.time()
        current_group = None
        for obj in query_iterator(self.query):
            if 'grouping' in config:
                next_group = getattr(obj, config['grouping'], u'')
                if current_group and current_group != next_group:
                    output.writerow([next_group])
                current_group = next_group

            row = self.create_row(obj)
            output.writerow(fixer(row))

            if time.time() - self.maxseconds > start:
                csvwriter.writerow(['truncated ...'])
                break

    def to_csv(self, fileobj, config=None):
        """Generate CSV in fileobj"""

        if config is None:
            config = {}

        csvwriter = csv.writer(fileobj, dialect='excel', delimiter='\t')
        fixer = lambda row: [unicode(x).encode('utf-8') for x in row]
        self.create_header(csvwriter, config, fixer)
        self.create_rows(csvwriter, config, )

    def to_xls(self, fileobj, config=None):
        """Generate XLS in fileobj"""

        import huTools.structured_xls

        if config is None:
            config = {}

        xlswriter = huTools.structured_xls.XLSwriter()
        self.create_header(xlswriter, config)
        self.create_rows(xlswriter, config)
        xlswriter.save(fileobj)
