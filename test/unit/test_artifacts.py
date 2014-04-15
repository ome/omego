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

import os

import omego
from omego.framework import Stop
import omego.artifacts
from omego.artifacts import Artifacts, ArtifactException
from omego.external import External


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
            self.unzip = '/test/unzip'
            self.unzipargs = '-unzipargs'
            self.unzipdir = 'unzip/dir'

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.UnsetStubs()

    def partial_mock_artifacts(self, matrix):
        # Artifacts.__init__ does a lot of work, so we can't just
        # stubout methods after constructing it
        self.mox.StubOutWithMock(omego.artifacts.opener, 'open')
        if matrix:
            omego.artifacts.opener.open(
                self.MockUrl.unlabelledurl + 'api/xml').AndReturn(
                self.MockUrl(True))
        omego.artifacts.opener.open(
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

    @pytest.mark.parametrize('matchdir', [True, False])
    @pytest.mark.parametrize('correctdir', [True, False])
    def test_unzip(self, matchdir, correctdir):
        self.mox.StubOutWithMock(External, 'run')
        self.mox.StubOutWithMock(os.path, 'isdir')

        External.run('/test/unzip', [
            '-unzipargs', '-d', 'unzip/dir', 'test.zip']).AndReturn(('', ''))
        if matchdir:
            os.path.isdir('unzip/dir/test').AndReturn(correctdir)

        self.mox.ReplayAll()

        a = self.partial_mock_artifacts(True)
        if correctdir or (not correctdir and not matchdir):
            assert a.unzip('test.zip', matchdir) == 'unzip/dir/test'
        else:
            with pytest.raises(Exception):
                a.unzip('test.zip')
        self.mox.VerifyAll()

    @pytest.mark.parametrize('exists', [True, False])
    @pytest.mark.parametrize('remote', [True, False])
    @pytest.mark.parametrize('overwrite', ['error', 'backup', 'keep'])
    def test_get_as_local_path(self, exists, remote, overwrite):
        if remote:
            p = 'http://example.org/test.zip'
            expectedp = 'test.zip'
        else:
            p = '/example/test.zip'
            expectedp = p
        a = self.partial_mock_artifacts(True)

        self.mox.StubOutWithMock(os.path, 'exists')
        self.mox.StubOutWithMock(os.path, 'isdir')
        self.mox.StubOutWithMock(omego.artifacts, 'rename_backup')
        self.mox.StubOutWithMock(omego.artifacts, 'download')

        if remote:
            os.path.exists(expectedp).AndReturn(exists)

        if remote and exists and overwrite == 'backup':
            omego.artifacts.rename_backup(expectedp)
            omego.artifacts.download(p, expectedp, 0)

        if remote and not exists:
            omego.artifacts.download(p, expectedp, 0)

        if not remote or (remote and not exists) or (
                remote and exists and overwrite != 'error'):
            os.path.isdir(expectedp).AndReturn(False)
            os.path.exists(expectedp).AndReturn(True)

        self.mox.ReplayAll()

        if remote and exists and overwrite == 'error':
            with pytest.raises(ArtifactException):
                a.get_as_local_path(p, overwrite=overwrite)
        else:
            ptype, lpath = a.get_as_local_path(p, overwrite=overwrite)
            assert ptype == 'file'
            assert lpath == expectedp

        self.mox.VerifyAll()


    # TODO
    # def test_download(self):
    #    pass
