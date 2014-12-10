#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/comp.py compability layer for App Engine

Created by Dr. Maximillian Dornseif on 2014-12-10.
Copyright (c) 2014 HUDORA GmbH. All rights reserved.
"""

from urllib import unquote

from google.appengine.ext import db
from google.appengine.ext import ndb

def xdb_kind(model_class):
    """Get kind from db or ndb model class"""
    kind = getattr(model_class, '_get_kind', None)
    if not kind:
        kind = getattr(model_class, 'kind', None)
        if not kind:
            return model_class.__name__
    return kind()

def xdb_get(model_class, encoded_key):
    """Ermittle die Instanz über den gegeben ID"""
    if issubclass(model_class, ndb.Model):
        key = ndb.Key(urlsafe=encoded_key)
        instance = key.get()
    elif issubclass(model_class, db.Model):
        instance = model_class.get(unquote(encoded_key))
    return instance

def xdb_is_ndb(model_class):
    if hasattr(model_class, 'all'):
        return False
    else:
        return True

def xdb_key(instance):
    if xdb_is_ndb(instance):
        return instance.key
    else:
        return instance.key()

def xdb_to_protobuf(instance):
    if xdb_is_ndb(instance):
        return ndb.ModelAdapter().entity_to_pb(instance).Encode()
    else:
        db.model_to_protobuf(instance).Encode()

def _get_queryset_db(model_class, ordering=None):
    """Queryset für Subklasse von db.Model"""
    query = model_class.all()
    if ordering:
        attr, direction = ordering
        if attr in model_class.properties():
            if direction == '-':
                attr = '-' + attr
            query.order(attr)
    return query

def _get_queryset_ndb(model_class, ordering):
    """Queryset für Subklasse von ndb.Model"""
    query = model_class.query()
    if ordering:
        attr, direction = ordering
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
    # TODO: Tupel: (attr, direction)
    if xdb_is_ndb(model_class):
        query = _get_queryset_ndb(model_class, ordering)
    else:
        query = _get_queryset_db(model_class, ordering)
    return query

