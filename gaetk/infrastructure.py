#!/usr/bin/env python
# encoding: utf-8
"""
infrastructure.py

Created by Maximillian Dornseif on 2011-01-07.
Copyright (c) 2011, 2012, 2016, 2017 Cyberlogi/HUDORA. All rights reserved.
"""
import logging
import re
import zlib

import google.appengine.ext.deferred.deferred

from gaetk import compat
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import ndb


# Tasks

def taskqueue_add_multi(qname, url, paramlist, **kwargs):
    """Adds more than one Task to the same Taskqueue/URL.

    tasks = []
    for kdnnr in kunden.get_changed():
        tasks.append(dict(kundennr=kdnnr))
    taskqueue_add_multi('softmq', '/some/path', tasks)
    """

    tasks = []
    for params in paramlist:
        tasks.append(taskqueue.Task(url=url, params=params, **kwargs))
        # Batch Addition to Taskqueue
        if len(tasks) >= 50:
            taskqueue.Queue(name=qname).add(tasks)
            tasks = []
    if tasks:
        taskqueue.Queue(name=qname).add(tasks)


def taskqueue_add_multi_payload(name, url, payloadlist, **kwargs):
    """like taskqueue_add_multi() but transmit a json encoded payload instead a query parameter.

    In the Task handler you can get the data via zdata = json.loads(self.request.body)`.
    See http://code.google.com/appengine/docs/python/taskqueue/tasks.html"""

    import huTools.hujson
    tasks = []
    for payload in payloadlist:
        payload = huTools.hujson.dumps(payload)
        payload = zlib.compress(payload)
        tasks.append(taskqueue.Task(url=url, payload=payload, **kwargs))
        # Patch Addition to Taskqueue
        if len(tasks) >= 50:
            taskqueue.Queue(name=name).add(tasks)
            tasks = []
    if tasks:
        taskqueue.Queue(name=name).add(tasks)


def defer(obj, *args, **kwargs):
    """Defers a callable for execution later.

    like https://cloud.google.com/appengine/articles/deferred
    but adds the function name to the url for easier debugging.

    Add this to `app.yaml`:
        handlers:
          # needed to allow abritary postfixes
          - url: /_ah/queue/deferred(.*)
            script: google.appengine.ext.deferred.deferred.application
            login: admin
    """
    def to_str(value):
        """Convert all datatypes to str"""
        if isinstance(value, unicode):
            return value.encode('ascii', 'ignore')
        return str(value)

    suffix = '{0}({1!s},{2!r})'.format(
        obj.__name__,
        ','.join(to_str(arg) for arg in args),
        ','.join('%s=%s' % (key, to_str(value)) for (key, value) in kwargs.items() if not key.startswith('_'))
    )
    suffix = re.sub(r'-+', '-', suffix.replace(' ', '-'))
    suffix = re.sub(r'[^/A-Za-z0-9_,.:@&+$\(\)\-]+', '', suffix)
    url = google.appengine.ext.deferred.deferred._DEFAULT_URL + '/' + suffix[:1600]
    kwargs["_url"] = kwargs.pop("_url", url)
    kwargs["_target"] = kwargs.pop("_target", 'workers')
    kwargs["_queue"] = kwargs.pop("_queue", 'workersq')
    try:
        return deferred.defer(obj, *args, **kwargs)
    except taskqueue.TaskAlreadyExistsError:
        logging.info('Task already exists')
    except taskqueue.TombstonedTaskError:
        logging.info('Task did already run')


# Datastore

def query_iterator(query, limit=50):
    """Iterates over a datastore query while avoiding timeouts via a cursor."""
    cursor = None
    while True:
        bucket, cursor, more_objects = compat.xdb_fetch_page(query, limit, start_cursor=cursor)
        if not bucket:
            break
        for entity in bucket:
            yield entity
        if not more_objects:
            break


def copy_entity(e, **extra_args):
    """Copy entity but change values in kwargs."""
    # see https://stackoverflow.com/a/2712401
    klass = e.__class__
    props = dict((v._code_name, v.__get__(e, klass)) for v in klass._properties.itervalues() if type(v) is not ndb.ComputedProperty)
    props.update(extra_args)
    return klass(**props)

def write_on_change(model, key, data, flush_cache=False):
    """Schreibe (nur) die geänderten Daten in den Datastore."""

    key_name = data[key]
    obj = compat.get_by_id_or_name(model, key_name)
    if obj is None:
        obj = model(key=compat.xdb_create_key(model, key_name), **data)
        obj.put()
        return obj

    changed, obj = write_on_change_instance(obj, data)
    if flush_cache and changed:
        flush_ndb_cache(obj)

    return obj


def write_on_change_instance(obj, data):
    """Schreibe Instanz mit geänderten Daten in Datastore."""

    properties = compat.xdb_properties(obj)
    dirty = False
    for key, value in data.iteritems():
        if value != getattr(obj, key, None):
            setattr(obj, key, value)
            dirty = True
    if dirty:
        obj.put()

    return dirty, obj

def flush_ndb_cache(instance):
    """
    Flush memcached ndb instance.

    Especially usefull if you mix (old) db and ndb for a model.
    """
    key = ndb.Context._memcache_prefix + compat.xdb_str_key(compat.xdb_key(instance))
    memcache.delete(key)


def reload_obj(obj):
    """Objekt ohne Cache neu laden."""
    if compat.xdb_is_ndb(obj):
        return obj.key.get(use_cache=False, use_memcache=False)
    else:
        return db.get(obj.key())
