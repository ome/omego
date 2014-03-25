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


import pytest  # noqa

from restview.restviewhttp import RestViewer


class TestReadme(object):

    def setup_method(self, method):
        self.viewer = RestViewer('.')
        self.viewer.css_path = self.viewer.css_url = None
        self.viewer.strict = True

    def teardown_method(self, method):
        pass

    def testValidRst(self, capsys):
        self.viewer.rest_to_html(''' Some text ''').strip()
        out, err = capsys.readouterr()
        assert err.rstrip() == ''

    def testBrokenRst(self, capsys):
        self.viewer.rest_to_html(''' Some text with an `error ''').strip()
        out, err = capsys.readouterr()
        assert err.rstrip() != ''

    def testReadme(self, capsys):
        with open('README.rst', 'r') as f:
            self.viewer.rest_to_html(f.read()).strip()
        out, err = capsys.readouterr()
        assert err.rstrip() == ''
