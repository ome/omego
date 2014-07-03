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

import pytest

from yaclifw.framework import main
from omego.artifacts import DownloadCommand

from integration_test_library import create_config_file


class TestDownload(object):

    def setup_class(self):
        self.artifact = 'cpp'

    def download(self, *args):
        args = ["download", self.artifact] + list(args)
        main("omego", args=args, parse_config_files=['-c', '--conffile'],
             items=[("download", DownloadCommand)])

    @pytest.mark.parametrize('conffile', [True, False])
    def testDownloadNoUnzip(self, tmpdir, conffile):
        with tmpdir.as_cwd():
            if conffile:
                cfg1 = tmpdir.join('f1.cfg')
                create_config_file(cfg1, download={'skipunzip': True})
                self.download('-c', str(cfg1))
            else:
                self.download('--skipunzip')
            assert len(tmpdir.listdir(
                lambda f: not str(f).endswith('f1.cfg'))) == 1

    def testDownloadUnzip(self, tmpdir):
        with tmpdir.as_cwd():
            self.download()
            files = tmpdir.listdir()
            assert len(files) == 2

    @pytest.mark.parametrize('conffile', [True, False])
    def testDownloadUnzipDir(self, tmpdir, conffile):
        with tmpdir.as_cwd():
            if conffile:
                cfg1 = tmpdir.join('f1.cfg')
                create_config_file(cfg1, download={'unzipdir': 'OMERO.cpp'})
                self.download('-c', str(cfg1))
            else:
                self.download('--unzipdir', 'OMERO.cpp')
            assert tmpdir.ensure('OMERO.cpp', dir=True)
