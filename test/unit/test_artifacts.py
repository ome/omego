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

from builtins import str
from builtins import object
import pytest
from mox3 import mox

from yaclifw.framework import Stop
from omego.artifacts import ArtifactException, ArtifactsList
from omego.artifacts import Artifacts, JenkinsArtifacts, ReleaseArtifacts
# Import whatever XML module was imported in omego.artifacts to avoid dealing
# with different versions
from omego.artifacts import XML
from omego import fileutils


class TestArtifactsList(object):

    def setup_class(self):
        self.urls = (
            'http://example.org/0.0.0/a/OMERO.insight-0.0.0.zip',
            'http://example.org/0.0.0/a/OMERO.insight-ij-0.0.0.zip',
            'http://example.org/0.0.0/a/OMERO.insight-0.0.0-mac_Java7+.zip',
            'http://example.org/0.0.0/a/GIT_INFO',
            'http://example.org/0.0.0/a/bioformats-0.0.0-DEV.zip',
            'http://example.org/0.0.0/a/bio-formats_plugins.jar',
            'http://example.org/0.0.0/a/bio-formats-tools.jar',
            'http://example.org/0.0.0/a/OMERO.server-0.0.0-DEV.zip',
        )

    def test_find_artifacts(self):
        a = ArtifactsList()
        a.find_artifacts(self.urls)

        assert a.get('insight') == self.urls[0]
        assert a.get('OMERO.insight-0.0.0.zip') == self.urls[0]
        assert a.get('insight-ij') == self.urls[1]
        assert a.get('mac') == self.urls[2]
        assert a.get('GIT_INFO') == self.urls[3]
        assert a.get('bio') == self.urls[4]
        assert a.get('bio-formats') == self.urls[6]

        with pytest.raises(ArtifactException):
            a.get('non-existent')

    def test_str(self):
        a = ArtifactsList()
        a.find_artifacts(self.urls)
        expected = """named-components:
  mac
  server
omerozips:
  insight-0.0.0
  insight-0.0.0-mac_Java7+
  insight-ij-0.0.0
  server-0.0.0-DEV
zips:
  OMERO.insight-0.0.0
  OMERO.insight-0.0.0-mac_Java7+
  OMERO.insight-ij-0.0.0
  OMERO.server-0.0.0-DEV
  bioformats-0.0.0-DEV
jars:
  bio-formats-tools
  bio-formats_plugins"""

        assert str(a) == expected


class MockAuth(object):
    httpuser = 'foo'
    httppassword = 'bar'


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


class MockDownloadUrl(object):
    downloadurl = 'http://example.org'
    latesturl = 'http://example.org/latest/omero'
    pageurl = 'http://example.org/omero/0.0.0/'
    artifactnames = [
        'OMERO.server-0.0.0-ice34-b1.zip', 'OMERO.server-0.0.0-ice35-b1.zip']
    artifactpath = 'artifacts/'

    def __init__(self, page):
        self.code = 200
        if page:
            self.url = self.pageurl
        else:
            self.url = '%s%s%s' % (
                self.pageurl, self.artifactpath, self.artifactnames[1])

    def read(self):
        return (
            '<html><body><a href="%s">%s</a>'
            '<a href="%s">%s</a></body></html>' % (
                self.artifactnames[0],
                self.artifactnames[0],
                self.artifactnames[1], self.artifactnames[1]))

    def close(self):
        pass


class Args(object):
    def __init__(self, matrix):
        if matrix:
            self.labels = 'label=foo,'
            self.build = MockUrl.unlabelledurl
        else:
            self.labels = ''
            self.build = MockUrl.labelledurl
        self.ci = 'https://ci.openmicroscopy.org'
        self.ice = None
        self.dry_run = False
        self.verbose = False
        self.skipunzip = False
        self.unzipdir = 'unzip/dir'
        self.overwrite = 'error'
        self.httpuser = MockAuth.httpuser
        self.httppassword = MockAuth.httppassword
        self.branch = 'TEST-build'
        self.downloadurl = MockDownloadUrl.downloadurl
        self.sym = None


class MoxBase(object):

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.UnsetStubs()


class TestJenkinsArtifacts(MoxBase):

    def partial_mock_artifacts(self, matrix):
        # JenkinsArtifacts.__init__ does a lot of work, so we can't just
        # stubout methods after constructing it
        self.mox.StubOutWithMock(fileutils, 'open_url')
        if matrix:
            fileutils.open_url(
                MockUrl.unlabelledurl + 'api/xml',
                httpuser=MockAuth.httpuser,
                httppassword=MockAuth.httppassword).AndReturn(
                MockUrl(True))
        fileutils.open_url(
            MockUrl.labelledurl + 'api/xml',
            httpuser=MockAuth.httpuser,
            httppassword=MockAuth.httppassword).AndReturn(
            MockUrl(False))
        self.mox.ReplayAll()
        return JenkinsArtifacts(Args(matrix))

    @pytest.mark.parametrize('matrix', [True, False])
    def test_init(self, matrix):
        # Also tests read_xml
        a = self.partial_mock_artifacts(matrix)
        assert a.get('server') == '%sartifact/%s' % (
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
        m = a.find_label_matches(urls, icever='3.5')
        assert m == urls[1]
        m = a.find_label_matches(urls, icever='3.4')
        assert m == urls[0]

        urls = [
            'http://example.org/x/ICE=3.3,label=foo,other=a/y',
            'http://example.org/x/ICE=3.3,label=foo,other=b/y'
            ]
        with pytest.raises(Stop):
            m = a.find_label_matches(urls, icever='3.5')

        urls = [
            'http://example.org/x/ICE=3.5,label=foo,other=a/y',
            'http://example.org/x/ICE=3.5,label=foo,other=b/y'
            ]
        with pytest.raises(Stop):
            m = a.find_label_matches(urls, icever='3.5')

        self.mox.VerifyAll()

    def test_label_list_parser(self):
        a = self.partial_mock_artifacts(True)
        labels = a.label_list_parser(
            'http://example.org/x/ICE=3.5,label=foo/y')
        assert labels == set(['ICE=3.5', 'label=foo'])
        self.mox.VerifyAll()


class TestReleaseArtifacts(MoxBase):

    def partial_mock_artifacts(self, release):
        # ReleaseArtifacts.__init__ does a lot of work, so we can't just
        # stubout methods after constructing it
        self.mox.StubOutWithMock(fileutils, 'dereference_url')
        if release == 'latest':
            fileutils.dereference_url(MockDownloadUrl.latesturl).AndReturn(
                MockDownloadUrl.pageurl)
        if release == '0.0':
            fileutils.dereference_url(
                MockDownloadUrl.latesturl + '0.0').AndReturn(
                    MockDownloadUrl.pageurl)

        self.mox.StubOutWithMock(fileutils, 'open_url')
        fileutils.open_url(
            MockDownloadUrl.pageurl +
            MockDownloadUrl.artifactpath).AndReturn(
            MockDownloadUrl(True))
        self.mox.ReplayAll()
        args = Args(False)
        args.branch = release
        return ReleaseArtifacts(args)

    @pytest.mark.parametrize('release', ['latest', '0.0', '0.0.0'])
    def test_init(self, release):
        # Also tests follow_latest_redirect
        a = self.partial_mock_artifacts(release)
        assert a.get('server') == '%s%s%s' % (
            MockDownloadUrl.pageurl, MockDownloadUrl.artifactpath,
            MockDownloadUrl.artifactnames[1])
        self.mox.VerifyAll()

    def test_read_downloads(self):
        self.mox.StubOutWithMock(fileutils, 'open_url')
        fileutils.open_url(
            MockDownloadUrl.pageurl + MockDownloadUrl.artifactpath).AndReturn(
            MockDownloadUrl(True))
        self.mox.ReplayAll()

        fullpath = '%s%s' % (
            MockDownloadUrl.pageurl, MockDownloadUrl.artifactpath)
        assert ReleaseArtifacts.read_downloads(
            MockDownloadUrl.pageurl + MockDownloadUrl.artifactpath) == {
            'ice34': [fullpath + MockDownloadUrl.artifactnames[0]],
            'ice35': [fullpath + MockDownloadUrl.artifactnames[1]]
            }
        self.mox.VerifyAll()


class TestArtifacts(MoxBase):

    class MockArtifacts(Artifacts):
        def __init__(self, component, url):
            class A(object):
                def get(self, c):
                    assert c == component
                    return url

            self.args = Args(False)
            self.artifacts = A()

    @pytest.mark.parametrize('auth', [
        {'httpuser': 'foo', 'httppassword': 'bar'}
    ])
    def test_download(self, auth):
        url = 'http://example.org/test/component-0.0.0.zip'
        a = self.MockArtifacts('testcomponent', url)

        self.mox.StubOutWithMock(fileutils, 'get_as_local_path')
        self.mox.StubOutWithMock(fileutils, 'unzip')
        fileutils.get_as_local_path(
            url, 'error', progress=0, httpuser=auth['httpuser'],
            httppassword=auth['httppassword']).AndReturn(
            ('file', 'component-0.0.0.zip'))
        fileutils.unzip('component-0.0.0.zip', match_dir=True,
                        destdir='unzip/dir').AndReturn('component-0.0.0')

        self.mox.ReplayAll()

        assert a.download('testcomponent') == 'component-0.0.0'

        self.mox.VerifyAll()
