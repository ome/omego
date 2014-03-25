#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2014 University of Dundee & Open Microscopy Environment
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

import pytest
import mox

import omego
from omego.framework import Stop
from omego.artifacts import Artifacts


class TestArtifacts(object):

    class Args(object):
        def __init__(self):
            self.build = 'http://example.org/jenkins/'
            self.labels = 'label=foo,ICE=3.5'

    class MockUrl(object):
        def __init__(self):
            self.code = 200
            self.url = 'http://example.org/jenkins/api/xml'

        def read(self):
            return (
                '<root>'
                '<artifact><fileName>OMERO.server-0.0.0-ice35-b0.zip'
                '</fileName><relativePath>OMERO.server-0.0.0-ice35-b0.zip'
                '</relativePath></artifact></root>')

        def close(self):
            pass

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.VerifyAll()
        self.mox.UnsetStubs()

    def partial_mock_artifacts(self):
        # Artifacts.__init__ does a lot of work, so we can't just
        # stubout methods after constructing it
        url = self.MockUrl()
        self.mox.StubOutWithMock(omego.artifacts.opener, 'open')
        omego.artifacts.opener.open(url.url).AndReturn(self.MockUrl())
        self.mox.ReplayAll()
        return Artifacts(self.Args())

    def test_init(self):
        # Also tests read_xml
        self.partial_mock_artifacts()

    def test_find_label_matches(self):
        a = self.partial_mock_artifacts()

        urls = [
            'http://example.org/x/ICE=3.4,label=foo/y',
            'http://example.org/x/ICE=3.5,label=foo/y'
            ]
        m = a.find_label_matches(urls)
        assert m == urls[1]

        urls = [
            'http://example.org/x/ICE=3.3,label=foo,other=a/y',
            'http://example.org/x/ICE=3.3,label=foo,other=b/y'
            ]
        with pytest.raises(Stop):
            m = a.find_label_matches(urls)

        urls = [
            'http://example.org/x/ICE=3.5,label=foo,other=a/y',
            'http://example.org/x/ICE=3.5,label=foo,other=b/y'
            ]
        with pytest.raises(Stop):
            m = a.find_label_matches(urls)

    def test_label_list_parser(self):
        a = self.partial_mock_artifacts()
        labels = a.label_list_parser(
            'http://example.org/x/ICE=3.5,label=foo/y')
        assert labels == set(['ICE=3.5', 'label=foo'])

    # TODO
    #def test_download(self):
    #    pass
