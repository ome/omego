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

from omego.framework import main
from omego.artifacts import DownloadCommand


class TestDownload(object):

    def setup_class(self):
        self.artifact = 'cpp'

    def download(self, *args):
        args = ["download", self.artifact] + list(args)
        main(args=args, items=[("download", DownloadCommand)])

    def testDownloadNoUnzip(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--skipunzip')
            files = tmpdir.listdir()
            assert len(files) == 1

    def testDownloadUnzip(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--unzipargs=-q')
            files = tmpdir.listdir()
            assert len(files) == 2

    def testDownloadUnzipDir(self, tmpdir):
        with tmpdir.as_cwd():
            self.download('--unzipargs=-q', '--unzipdir', 'OMERO.cpp')
            assert tmpdir.ensure('OMERO.cpp', dir=True)
