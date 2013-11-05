#!/usr/bin/env python
# encoding: utf-8
"""
handler_test.py

Tests for gaetk.handler

Created by Benjamin Köppchen on 2011-10-18.
Copyright (c) 2011 HUDORA GmbH. All rights reserved.
"""
import unittest

from google.appengine.ext import db
import unittest
import gaetk
from mock import Mock
import webtest
from huTools.hujson import loads

from gaetk.gaesessions import SessionMiddleware


class Widget(db.Model):
    number = db.IntegerProperty()

    def to_dict(self):
        return {'number': self.number}


class TestHandler(gaetk.handler.JsonResponseHandler):
    def get(self):
        return self.paginate(Widget.all().order('number'), 3, calctotal=True)


class TestPagination(unittest.TestCase):
    """Tests for `gaetk.handler.BasisHandler.pagination`"""

    def setUp(self):
        """Sets up an application with the Testhandler, and creates 8 `Widget`s"""
        for i in range(10):
            Widget(number=i).put()

        wsgiapp = gaetk.webapp2.WSGIApplication([(r'/', TestHandler)])
        wsgiapp = SessionMiddleware(wsgiapp, cookie_key='this should be a 32 character key')
        self.app = webtest.TestApp(wsgiapp)

    def _get_json(self, url):
        """helper: requests the url as json"""
        response = self.app.get(url)
        return loads(response.body)

    def test_pagination_per_start(self):
        """Test iteration over a pagination by `start` parameter."""
        data = self._get_json('/')
        self.assertEquals(data['total'], 10)
        self.assertEquals(data['next_start'], 3)
        self.assertEquals(data['more_objects'], True)
        self.assertEquals(data['objects'], [{'number': nr} for nr in range(0, 3)])

        data = self._get_json('/?start=3')
        self.assertEquals(data['total'], 10)
        self.assertEquals(data['next_start'], 6)
        self.assertEquals(data['more_objects'], True)
        self.assertEquals(data['objects'], [{'number': nr} for nr in range(3, 6)])

        data = self._get_json('/?start=8')
        self.assertEquals(data['more_objects'], False)
        self.assertEquals(data['objects'], [{'number': nr} for nr in range(8, 10)])

    def test_pagination_per_cursor(self):
        """Testet das Iterieren über eine Pagination per cursor."""
        data = self._get_json('/')
        self.assertEquals(data['objects'], [{'number': nr} for nr in range(0, 3)])
        self.assertTrue('cursor' in data)

        data = self._get_json('/?cursor=%s' % data['cursor'])
        self.assertEquals(data['objects'], [{'number': nr} for nr in range(4, 7)])
        self.assertTrue('cursor' in data)

        data = self._get_json('/?cursor=%s' % data['cursor'])
        self.assertEquals(data['objects'], [{'number': nr} for nr in range(7, 10)])
        self.assertTrue('cursor' in data)

        data = self._get_json('/?cursor=%s' % data['cursor'])
        self.assertEquals(data['objects'], [])
        self.assertTrue('cursor' in data)

    def tearDown(self):
        """Remove all `Widget`s"""
        db.delete(Widget.all())


if __name__ == '__main__':
    unittest.main()
