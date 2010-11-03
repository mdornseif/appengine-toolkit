#!/usr/bin/env python
# encoding: utf-8
"""
gaetk/extjs.py - helpers for appengine with ExtJS

Created by Maximillian Dornseif on 2010-10-31.
Copyright (c) 2010 HUDORA. All rights reserved.
"""


def model2formconfig(model):
    ret = []
    for k, v in model.properties().items():
        #print v.default_value()

        d = dict(name=v.name,
                 fieldLabel=(v.verbose_name or v.name),
                 allowBlank=(v.required == False))
        if 'Boolean' in str(type(v)):
            d['xtype'] = 'checkbox'
        if v.choices:
            d['xtype'] = 'combo'
            d['store'] = v.choices
        ret.append(d)
    return ret
