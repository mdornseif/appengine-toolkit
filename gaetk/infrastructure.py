#!/usr/bin/env python
# encoding: utf-8
"""
infrastructure.py

Created by Maximillian Dornseif on 2011-01-07.
Copyright (c) 2011, 2012 HUDORA. All rights reserved.
"""

from google.appengine.api import taskqueue
import zlib


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


def query_iterator(query, limit=50):
    """Iterates over a datastore query while avoiding timeouts via a cursor."""
    cursor = None
    while True:
        if cursor:
            query.with_cursor(cursor)
        bucket = query.fetch(limit=limit)
        if not bucket:
            break
        for entity in bucket:
            yield entity
        cursor = query.cursor()


def copy_entity(entity, **kwargs):
    """Copy entity"""
    klass = type(entity)
    properties = dict((key, value.__get__(entity, klass)) for (key, value) in klass.properties().iteritems())
    properties.update(**kwargs)
    return klass(**properties)


def index_usages(query):
    """
    Format used indexes nicely.

    Darstellung wie in index.yaml:
    yaml.dump(desc, default_flow_style=False)
    """
    indexes = []
    for index in query.index_list():
        description = dict(kind=str(index.kind()))
        if index.has_ancestor():
            description['ancestor'] = True
        properties = description['properties'] = []
        for name, direction in index.properties():
            prop = dict(name=str(name))
            if direction == db.Index.DESCENDING:
                prop['direction'] = 'desc'
            properties.append(prop)
        indexes.append(description)

    return indexes
