# encoding: utf-8
"""
forms.py - utility functions for form handling

Created by Christian Klein on 2017-02-28.
Copyright (c) 2017 HUDORA. All rights reserved.
"""


def get_changelist(form, obj, ignore=None):
    """
    Erstelle Liste mit Änderungen

    Als Parameter wird ein validiertes Formular und das zugehörige Objekt erwartet.
    Rückgabewert ist eine Liste von Dreitupeln bestehend aus dem Feldnamen,
    dem Wert aus dem Formular und dem bestehenden Wert des Objekts.
    """

    if ignore is None:
        ignore = []

    changes = []
    for field in form:
        if field.name not in ignore and hasattr(obj, field.name):
            form_value, obj_value = field.data, getattr(obj, field.name)
            if form_value != obj_value:
                changes.append((field.name, form_value, obj_value))
    return changes
