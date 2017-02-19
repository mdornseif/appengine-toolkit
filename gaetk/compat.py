#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/compat.py compability layer for App Engine

Created by Dr. Maximillian Dornseif on 2014-12-10.
Copyright (c) 2014, 2016 HUDORA GmbH. All rights reserved.
"""
from urllib import unquote

from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext import db
from google.appengine.ext import ndb
from google.appengine.ext.ndb import model


def xdb_create_key(model_class, id_or_name, parent=None):
    """Key creation."""
    if issubclass(model_class, ndb.Model):
        return ndb.Key(model_class._get_kind(), id_or_name, parent=parent)
    else:
        return db.Key.from_path(model_class.kind(), id_or_name, parent=parent)


def get_by_id_or_name(model_class, id_or_name, parent=None, **kwargs):
    """Getting by key value."""
    if issubclass(model_class, ndb.Model):
        return model_class.get_by_id(id_or_name, parent=parent, **kwargs)
    else:
        return model_class.get_by_key_name(id_or_name, parent=parent, **kwargs)


def xdb_kind(model_class):
    """Get kind (table-name, string) for ndb model class"""
    kind = getattr(model_class, '_get_kind', None)
    if not kind:
        kind = getattr(model_class, 'kind', None)
        if not kind:
            return model_class.__name__
    return kind()


def xdb_kind_from_query(query):
    """Get kind-Model-Object from db or ndb model class"""

    if getattr(query, 'kind', None):
        return model.Model._lookup_model(query.kind)
    return query._model_class


def xdb_get_instance(model_class, encoded_key):
    """Ermittle die Instanz über den gegeben ID"""
    if issubclass(model_class, ndb.Model):
        key = ndb.Key(urlsafe=encoded_key)
        instance = key.get()
    else:
        instance = model_class.get(unquote(encoded_key))
    return instance


def xdb_get(key):
    """Gent an entity."""
    if isinstance(key, ndb.key.Key):
        return key.get()
    else:
        return db.get(key)


def xdb_is_ndb(model_class):
    """Check if instance is ndb or db."""
    if hasattr(model_class, 'all'):
        return False
    else:
        return True


def xdb_key(instance):
    """Return key."""
    if xdb_is_ndb(instance):
        return instance.key
    else:
        return instance.key()


def xdb_id_or_name(key):
    """Return key-name (or id)."""
    if isinstance(key, ndb.key.Key):
        return key.id()
    else:
        return key.id_or_name()


def xdb_to_protobuf(instance):
    """Convert an instance to a protobuuf."""
    if xdb_is_ndb(instance):
        return ndb.ModelAdapter().entity_to_pb(instance).Encode()
    else:
        db.model_to_protobuf(instance).Encode()


def xdb_properties(instance):
    """Properties einer Entity."""
    if xdb_is_ndb(instance):
        return instance._properties
    else:
        return instance.properties()


def _get_queryset_db(model_class, ordering=None):
    """Queryset für Subklasse von db.Model"""
    query = model_class.all()
    if ordering:
        attr, direction = ordering  # pylint: disable=unpacking-non-sequence
    else:
        attr, direction = None, None

    if attr and attr in model_class.properties():
        if direction == '-':
            attr = '-' + attr
        query.order(attr)
    return query


def _get_queryset_ndb(model_class, ordering=None):
    """Queryset für Subklasse von ndb.Model"""
    query = model_class.query()
    if ordering:
        attr, direction = ordering  # pylint: disable=unpacking-non-sequence
        prop = model_class._properties.get(attr)
        if prop:
            if direction == '-':
                return query.order(-prop)
            else:
                return query.order(prop)
    return query


def xdb_queryset(model_class, ordering=None):
    """Gib das QuerySet für die Admin-Seite zurück

    Es wird die gewünschte Sortierung durchgeführt.
    """
    if xdb_is_ndb(model_class):
        query = _get_queryset_ndb(model_class, ordering)
    else:
        query = _get_queryset_db(model_class, ordering)
    return query


def xdb_query_run(query):
    """Erzeugt einen Iterator basierend auf einer query."""
    if isinstance(query, ndb.Query):
        return query()
    else:
        return query.run()
    return query


def xdb_fetch_page(query, limit, offset=None, start_cursor=None):
    """Pagination-ready fetching a some entities."""

    if isinstance(query, ndb.Query):
        if start_cursor:
            if isinstance(start_cursor, basestring):
                start_cursor = Cursor(urlsafe=start_cursor)
            objects, cursor, more_objects = query.fetch_page(limit, start_cursor=start_cursor)
        else:
            objects, cursor, more_objects = query.fetch_page(limit, offset=offset)
    elif isinstance(query, db.Query) or isinstance(query, db.GqlQuery):
        if start_cursor:
            if isinstance(start_cursor, Cursor):
                start_cursor = start_cursor.urlsafe()
            query.with_cursor(start_cursor)
            objects = query.fetch(limit)
            cursor = Cursor(urlsafe=query.cursor())
            more_objects = len(objects) == limit
        else:
            objects = query.fetch(limit, offset=offset)
            # MultiQuery kann keine Cursor
            if len(getattr(query, '_Query__query_sets', [])) < 2:
                _cursor = query.cursor()
                more_objects = query.with_cursor(_cursor).count(1) > 0
                cursor = Cursor(urlsafe=_cursor)
            else:
                more_objects = len(objects) == limit
                cursor = None
    else:
        raise RuntimeError('unknown query class: %s' % type(query))
    return objects, cursor, more_objects


def xdb_str_key(key):
    """Stringrepräsentation eines Keys"""
    if isinstance(key, ndb.key.Key):
        return key.urlsafe()
    else:
        return str(key)


def xdb_prop_name(prop):
    if isinstance(prop, ndb.Property):
        return prop._name
    elif isinstance(prop, db.Property):
        return prop.name


def xdb_prop_creation_counter(prop):
    if isinstance(prop, ndb.Property):
        return prop._creation_counter
    elif isinstance(prop, db.Property):
        return prop.creation_counter
