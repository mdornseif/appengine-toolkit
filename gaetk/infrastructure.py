#!/usr/bin/env python
# encoding: utf-8
"""
infrastructure.py

Created by Maximillian Dornseif on 2011-01-07.
Copyright (c) 2011 HUDORA. All rights reserved.
"""

from google.appengine.api import taskqueue
import zlib


def taskqueue_add_multi(name, url, paramlist, **kwargs):
    """Adds more than one Task to the same Taskqueue/URL.

    tasks = []
    for kdnnr in kunden.get_changed():
        tasks.append(dict(kundennr=kdnnr))
    taskqueue_add_multi(name='softmq', url='/some/path', tasks)
    """

    tasks = []
    for params in paramlist:
        tasks.append(taskqueue.Task(url=url, params=params, **kwargs))
        # Patch Addition to Taskqueue
        if len(tasks) >= 100:
            taskqueue.Queue(name=name).add(tasks)
            tasks = []
    taskqueue.Queue(name=name).add(tasks)


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
        if len(tasks) >= 100:
            taskqueue.Queue(name=name).add(tasks)
            tasks = []
    taskqueue.Queue(name=name).add(tasks)

