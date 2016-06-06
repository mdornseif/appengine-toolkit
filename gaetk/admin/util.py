#!/usr/bin/env python
# encoding: utf-8
"""
util.py

Created by Christian Klein on 2011-08-10.
Copyright (c) 2011-2015 HUDORA GmbH. All rights reserved.
"""
import mimetypes

import cloudstorage
import config

from gaetk.compat import xdb_kind
from google.appengine.api import app_identity
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import ndb
from huTools.calendar.formats import convert_to_date
from huTools.calendar.formats import convert_to_datetime


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


def upload_to_blobstore(obj, key_name, blob):
    """
    Lade ein Datei-ähnliches Objekt in den Blobstore

    Der Rückgabewert ist der Blob-Key des neuen Objekts.
    """
    mime_type, _ = mimetypes.guess_type(blob.filename)
    bucket = getattr(config, 'GCS_BUCKET_NAME', app_identity.get_default_gcs_bucket_name())
    file_name = '/%s/admin/%s/%s/%s' % (bucket, xdb_kind(obj), key_name, blob.filename)
    with cloudstorage.open(file_name, 'w', content_type=mime_type) as fileobj:
        while blob.file:
            data = blob.file.read(8192)
            if not data:
                break
            fileobj.write(data)
    return blobstore.BlobKey(blobstore.create_gs_key('/gs' + file_name))


def call_hook(func, keystr):
    """Rufe einen Hook mit der Instanz als Parameter auf"""
    key = ndb.Key(urlsafe=keystr)
    instance = key.get()
    func(instance)
