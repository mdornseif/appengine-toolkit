#!/usr/bin/env python
# encoding: utf-8
"""
util.py

Created by Christian Klein on 2011-08-10.
Copyright (c) 2011 HUDORA GmbH. All rights reserved.
"""
from __future__ import with_statement
import config
config.imported = True

import mimetypes

from google.appengine.api import files
from google.appengine.ext import db
from huTools.calendar.formats import convert_to_date, convert_to_datetime


def get_app_name(model):
    """Django-like...

    >>> get_app_name('frontend.news.models.NewsItem')
    'news'
    >>> get_app_name('common.models.Sparepart')
    'Sparepart'
    """
    if not hasattr(model, '__module__'):
        return u''
    components = model.__module__.split('.')
    if len(components) > 3:
        return components[-3]
    elif len(components) > 2:
        return components[-2]
    else:
        return components[-1]


def create_instance(klass, data):
    """Erzeuge eine Instanz eines Models aus den übergebenen Daten"""

    # Falls das Model eine Methode 'create' besitzt, rufe diese auf.
    if hasattr(klass, 'create'):
        return klass.create(data)

    # Ansonsten wird ein generischer Ansatz verfolgt:
    tmp = {}
    props = klass.properties()

    for attr in data:
        if attr not in props:
            continue

        value = data[attr]
        prop = props[attr]

        if isinstance(prop, (db.StringProperty, db.TextProperty)):
            pass
        elif isinstance(prop, db.LinkProperty):
            pass
        elif isinstance(prop, db.DateProperty):
            value = convert_to_date(value)
        elif isinstance(prop, db.DateTimeProperty):
            value = convert_to_datetime(value)
        elif isinstance(prop, db.BooleanProperty):
            pass
        else:
            raise ValueError(u'Unknown property: %s', prop)

        tmp[attr.encode('ascii', 'replace')] = value

    return klass(**tmp)


def object_as_dict(obj):
    """Gib eine Repräsentation als dict zurück"""

    if hasattr(obj, 'as_dict'):
        fields = obj.as_dict()
    else:
        fields = dict((name, prop.get_value_for_datastore(obj)) for (name, prop) in obj.properties().items())

    model = '%s.%s' % (obj.__class__.__module__.split('.')[1], obj.kind())
    return {'model': model, 'key': str(obj.key()), 'fields': fields}


def upload_to_blobstore(fileobj):
    """
    Lade ein Datei-ähnliches Objekt in den Blobstore

    Der Rückgabewert ist der Blob-Key des neuen Objekts.
    """
    mime_type, _ = mimetypes.guess_type(fileobj.filename)
    filename = files.blobstore.create(mime_type=mime_type, _blobinfo_uploaded_filename=fileobj.filename)

    with files.open(filename, 'a') as blobstore_file:
        # In den Blobstore kann nur in einer Blockgröße von 1 MB geschrieben werden
        while fileobj.file:
            data = fileobj.file.read(990000)
            if not data:
                break
            blobstore_file.write(data)
    files.finalize(filename)
    return files.blobstore.get_blob_key(filename)
