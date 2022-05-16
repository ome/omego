#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2013-2014 University of Dundee & Open Microscopy Environment
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

from __future__ import division
from past.utils import old_div
from builtins import object
import pytest  # noqa

from yaclifw.framework import main
from omego.artifacts import DownloadCommand


class Downloader(object):

    def setup_class(self):
        self.artifact = None

    def download(self, *args):
        args = ["download", self.artifact] + list(args)
        main("omego", args=args, items=[("download", DownloadCommand)])


class TestDownloadJenkins(Downloader):

    def setup_class(self):
        self.artifact = 'java'
        self.branch = 'OMERO-build'
        self.ice = '3.6'

    def testDownloadNoUnzip(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--skipunzip', '--branch', self.branch,
                          '--ice', self.ice)
            files = tmpdir.listdir()
            assert len(files) == 1

    def testDownloadUnzip(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--branch', self.branch, '--ice', self.ice)
            files = tmpdir.listdir()
            assert len(files) == 2

    def testDownloadUnzipDir(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--unzipdir', 'OMERO.java', '--branch', self.branch,
                          '--ice', self.ice)
            expected = old_div(tmpdir, 'OMERO.java')
            assert expected.exists()
            assert expected.isdir()

    def testDownloadSym(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--branch', self.branch, '--ice', self.ice,
                          '--sym', 'auto')
            files = tmpdir.listdir()
            assert len(files) == 3

            expected = old_div(tmpdir, 'OMERO.java')
            assert expected.exists()
            assert expected.isdir()

            # Part two, if an artifact already exists and is unzipped check
            # that a new symlink is created if necessary
            self.download('--branch', self.branch, '--ice', self.ice,
                          '--sym', 'custom.sym')
            files2 = tmpdir.listdir()
            files2diff = set(files2).symmetric_difference(files)
            assert len(files2diff) == 1
            sym2 = files2diff.pop()
            assert sym2 == (old_div(tmpdir, 'custom.sym'))
            assert sym2.isdir()

    def testDownloadBuildNumber(self):
        # Old Jenkins artifacts are deleted so we can't download.
        # Instead assert that an AttributeError is raised.
        # This is not ideal since this error could occur for other reasons.
        branch = self.branch + ':600'
        with pytest.raises(AttributeError) as exc:
            self.download('--branch', branch, '--ice', self.ice)
        assert 'No artifacts' in exc.value.args[0]

    def testDownloadList(self, tmpdir):
        self.artifact = ''
        self.branch = 'latest'
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 0


class TestDownloadRelease(Downloader):

    def setup_class(self):
        # python and apic artifacts no longer exist
        self.artifact = 'java'

    def testDownloadRelease(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--release', 'latest', '--ice', '3.6')
            files = tmpdir.listdir()
            assert len(files) == 2

    def testDownloadNonExistingArtifact(self):
        with pytest.raises(AttributeError):
            self.download('-n', '--release', '5.3', '--ice', '3.3')


class TestDownloadBioFormats(Downloader):

    def setup_class(self):
        self.branch = 'BIOFORMATS-build'

    def testDownloadJar(self, tmpdir):
        self.artifact = 'formats-api'
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 1
            assert files[0].basename.endswith(".jar")
            assert files[0].basename.startswith('formats-api')


class TestDownloadGithub(Downloader):

    def setup_class(self):
        self.artifact = 'insight'

    def testDownloadGithub(self, tmpdir):
        with tmpdir.as_cwd():
            self.download(
                '--release', '5.5.8',
                '--github', 'ome/omero-insight',
                '--sym', 'auto')
        files = tmpdir.listdir()
        assert len(files) == 3
        print([f.basename for f in files])
        assert sorted(f.basename for f in files) == [
            'OMERO.insight',
            'OMERO.insight-5.5.8',
            'OMERO.insight-5.5.8.zip',
        ]
