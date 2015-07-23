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
from omego.artifacts import Artifacts, JenkinsArtifacts
# Import whatever XML module was imported in omego.artifacts to avoid dealing
# with different versions
from omego.artifacts import XML
from omego import fileutils


class MockUrl(object):
    build = 1
    oldbuild = 0
    labelledurl = 'http://example.org/jenkins/ICE=3.5,label=foo/1/'
    oldlabelledurl = 'http://example.org/jenkins/ICE=3.5,label=foo/0/'
    unlabelledurl = 'http://example.org/jenkins/1/'
    artifactname = 'OMERO.server-0.0.0-ice35-b1.zip'
    artifactpath = 'a/OMERO.server-0.0.0-ice35-b1.zip'

    def __init__(self, matrix):
        self.code = 200
        self.matrix = matrix
        self.url = self.unlabelledurl if matrix else self.labelledurl

    def read(self):
        if self.matrix:
            return (
                '<matrixBuild>'
                '<url>%s</url>'
                '<run><number>%d</number><url>%s</url></run>'
                '<run><number>%d</number><url>%s</url></run>'
                '</matrixBuild>' % (
                    self.unlabelledurl,
                    self.oldbuild, self.oldlabelledurl,
                    self.build, self.labelledurl))
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
            self.build = MockUrl.unlabelledurl
        else:
            self.labels = ''
            self.build = MockUrl.labelledurl
        self.dry_run = False
        self.verbose = False
        self.skipunzip = False
        self.unzipdir = 'unzip/dir'
        self.overwrite = 'error'
        self.httpuser = None
        self.httppassword = None


class MoxBase(object):

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.UnsetStubs()


class TestJenkinsArtifacts(MoxBase):

    def partial_mock_artifacts(self, matrix):
        # Artifacts.__init__ does a lot of work, so we can't just
        # stubout methods after constructing it
        self.mox.StubOutWithMock(fileutils, 'open_url')
        if matrix:
            fileutils.open_url(
                MockUrl.unlabelledurl + 'api/xml').AndReturn(
                MockUrl(True))
        fileutils.open_url(
            MockUrl.labelledurl + 'api/xml').AndReturn(
            MockUrl(False))
        self.mox.ReplayAll()
        return JenkinsArtifacts(Args(matrix))

    @pytest.mark.parametrize('matrix', [True, False])
    def test_init(self, matrix):
        # Also tests read_xml
        a = self.partial_mock_artifacts(matrix)
        assert hasattr(a, 'server')
        assert a.server == '%sartifact/%s' % (
            MockUrl.labelledurl, MockUrl.artifactpath)
        self.mox.VerifyAll()

    def test_get_latest_runs(self):
        a = self.partial_mock_artifacts(True)
        root = XML(MockUrl(True).read())
        runs = a.get_latest_runs(root)

        assert runs == [MockUrl.labelledurl]

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


class TestArtifacts(MoxBase):

    class MockArtifacts(Artifacts):
        def __init__(self, component, url):
            class A(object):
                pass

            self.args = Args(False)
            self.artifacts = A()
            setattr(self.artifacts, component, url)

    def test_download(self):
        url = 'http://example.org/test/component-0.0.0.zip'
        a = self.MockArtifacts('testcomponent', url)

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
