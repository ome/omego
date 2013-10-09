#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2013 University of Dundee & Open Microscopy Environment
# All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import sys
import unittest
from restview.restviewhttp import RestViewer
from StringIO import StringIO


class TestReadme(unittest.TestCase):

    def setUp(self):
        super(TestReadme, self).setUp()
        self.stderr = StringIO()
        self.saved_stderr = sys.stderr
        sys.stderr = self.stderr

        self.viewer = RestViewer('.')
        self.viewer.css_path = self.viewer.css_url = None
        self.viewer.strict = True

    def tearDown(self):
        self.stderr.close()
        sys.stderr = self.saved_stderr
        super(TestReadme, self).tearDown()

    def testValidRst(self):

        self.viewer.rest_to_html(''' Some text ''').strip()
        self.assertEqual(self.stderr.getvalue().rstrip(), '')

    def testBrokenRst(self):

        self.viewer.rest_to_html(''' Some text with an `error ''').strip()
        self.assertNotEqual(self.stderr.getvalue().rstrip(), '')

    def testReadme(self):

        try:
            f = open('README.rst', 'r')
            self.viewer.rest_to_html(f.read()).strip()
        finally:
            f.close()
        self.assertEqual(self.stderr.getvalue().rstrip(), '')

if __name__ == '__main__':
    unittest.main()
