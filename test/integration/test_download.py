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
        self.branch = 'OMERO-5.1-latest'

    def testDownloadNoUnzip(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--skipunzip', '--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 1

    def testDownloadUnzip(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 2

    def testDownloadUnzipDir(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--unzipdir', 'OMERO.py', '--branch', self.branch)
            assert tmpdir.ensure('OMERO.py', dir=True)

    def testDownloadRelease(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--release', 'latest')
            files = tmpdir.listdir()
            assert len(files) == 2


class TestDownloadBioFormats(Downloader):

    def setup_class(self):
        self.branch = 'BIOFORMATS-5.1-latest'

    def testDownloadJar(self, tmpdir):
        self.artifact = 'ij'
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 1
            assert files[0].basename == 'ij.jar'

    def testDownloadFullFilename(self, tmpdir):
        self.artifact = 'ij.jar'
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 1
            assert files[0].basename == 'ij.jar'


class TestDownloadList(Downloader):

    def setup_class(self):
        self.artifact = ''
        self.branch = 'latest'

    def testDownloadList(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--branch', self.branch)
            files = tmpdir.listdir()
            assert len(files) == 0
