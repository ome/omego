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

import pytest  # noqa

from yaclifw.framework import main
from omego.artifacts import DownloadCommand


class Downloader(object):

    def setup_class(self):
        self.artifact = None

    def download(self, *args):
        args = ["download", self.artifact] + list(args)
        main("omego", args=args, items=[("download", DownloadCommand)])


class TestDownload(Downloader):

    def setup_class(self):
        self.artifact = 'python'
        self.branch = 'OMERO-DEV-latest'
        self.ice = '3.5'

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
            self.download('--unzipdir', 'OMERO.py', '--branch', self.branch,
                          '--ice', self.ice)
            expected = tmpdir / 'OMERO.py'
            assert expected.exists()
            assert expected.isdir()

    def testDownloadSym(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--branch', self.branch, '--ice', self.ice,
                          '--sym', 'auto')
            files = tmpdir.listdir()
            assert len(files) == 3

            expected = tmpdir / 'OMERO.py'
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
            assert sym2 == (tmpdir / 'custom.sym')
            assert sym2.isdir()

    def testDownloadRelease(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--release', 'latest', '--ice', self.ice)
            files = tmpdir.listdir()
            assert len(files) == 2

    def testDownloadNonExistingArtifact(self):
        with pytest.raises(AttributeError):
            self.download('-n', '--release', '5.3', '--ice', '3.3')

    def testDownloadBuildNumber(self):
        # Old Jenkins artifacts are deleted so we can't download.
        # Instead assert that an AttributeError is raised.
        # This is not ideal since this error could occur for other reasons.
        branch = self.branch + ':600'
        with pytest.raises(AttributeError) as exc:
            self.download('--branch', branch, '--ice', self.ice)
        assert 'No artifacts' in exc.value.message


class TestDownloadBioFormats(Downloader):

    def setup_class(self):
        self.branch = 'BIOFORMATS-DEV-latest'

    def testDownloadJar(self, tmpdir):
        self.artifact = 'formats-api'
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 1
            assert files[0].basename == 'formats-api.jar'

    def testDownloadFullFilename(self, tmpdir):
        self.artifact = 'formats-api'
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 1
            assert files[0].basename == 'formats-api.jar'


class TestDownloadList(Downloader):

    def setup_class(self):
        self.artifact = ''
        self.branch = 'latest'

    def testDownloadList(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 0
