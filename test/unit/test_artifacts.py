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

from yaclifw.framework import Stop
from omego.artifacts import Artifacts
from omego import fileutils


class TestArtifacts(object):

    class MockUrl(object):
        labelledurl = 'http://example.org/jenkins/ICE=3.5,label=foo/'
        unlabelledurl = 'http://example.org/jenkins/'
        artifactname = 'OMERO.server-0.0.0-ice35-b0.zip'
        artifactpath = 'a/OMERO.server-0.0.0-ice35-b0.zip'

        def __init__(self, matrix):
            self.code = 200
            self.matrix = matrix
            self.url = self.unlabelledurl if matrix else self.labelledurl

        def read(self):
            if self.matrix:
                return (
                    '<matrixBuild><run><url>%s</url></run></matrixBuild>' %
                    self.labelledurl)
            return (
                '<root><artifact><fileName>%s</fileName><relativePath>'
                '%s</relativePath></artifact></root>' %
                (self.artifactname, self.artifactpath))

        def close(self):
            pass

    class Args(object):
        def __init__(self, matrix):
            if matrix:
                self.labels = 'label=foo,ICE=3.5'
                self.build = TestArtifacts.MockUrl.unlabelledurl
            else:
                self.labels = ''
                self.build = TestArtifacts.MockUrl.labelledurl
            self.dry_run = False
            self.verbose = False
            self.skipunzip = False
            self.unzipdir = 'unzip/dir'
            self.overwrite = 'error'
            self.httpuser = None
            self.httppassword = None

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.UnsetStubs()

    def partial_mock_artifacts(self, matrix):
        # Artifacts.__init__ does a lot of work, so we can't just
        # stubout methods after constructing it
        self.mox.StubOutWithMock(fileutils, 'open_url')
        if matrix:
            fileutils.open_url(
                self.MockUrl.unlabelledurl + 'api/xml').AndReturn(
                self.MockUrl(True))
        fileutils.open_url(
            self.MockUrl.labelledurl + 'api/xml').AndReturn(
            self.MockUrl(False))
        self.mox.ReplayAll()
        return Artifacts(self.Args(matrix))

    @pytest.mark.parametrize('matrix', [True, False])
    def test_init(self, matrix):
        # Also tests read_xml
        a = self.partial_mock_artifacts(matrix)
        assert hasattr(a, 'server')
        assert a.server == '%sartifact/%s' % (
            self.MockUrl.labelledurl, self.MockUrl.artifactpath)
        self.mox.VerifyAll()

    def test_find_label_matches(self):
        a = self.partial_mock_artifacts(True)

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
        self.mox.VerifyAll()

    def test_label_list_parser(self):
        a = self.partial_mock_artifacts(True)
        labels = a.label_list_parser(
            'http://example.org/x/ICE=3.5,label=foo/y')
        assert labels == set(['ICE=3.5', 'label=foo'])
        self.mox.VerifyAll()

    def test_download(self):
        a = self.partial_mock_artifacts(True)
        url = 'http://example.org/test/component-0.0.0.zip'
        setattr(a, 'testcomponent', url)

        self.mox.StubOutWithMock(fileutils, 'get_as_local_path')
        self.mox.StubOutWithMock(fileutils, 'unzip')
        fileutils.get_as_local_path(
            url, 'error', progress=0, httpuser=None,
            httppassword=None).AndReturn(
            ('file', 'component-0.0.0.zip'))
        fileutils.unzip('component-0.0.0.zip', match_dir=True,
                        destdir='unzip/dir').AndReturn('component-0.0.0')

        self.mox.ReplayAll()

        assert a.download('testcomponent') == 'component-0.0.0'

        self.mox.VerifyAll()
