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
