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

import unittest
import os
import shutil
import tempfile

from omego.framework import main
from omego.artifacts import DownloadCommand


class TestDownload(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.cwd = os.getcwd()
        self.path = tempfile.mkdtemp("", "download-", ".")
        self.path = os.path.abspath(self.path)
        os.chdir(self.path)
        self.artifact = 'win'

    def tearDown(self):
        try:
            shutil.rmtree(self.path)
        finally:
            # Return to cwd regardless.
            os.chdir(self.cwd)
        unittest.TestCase.tearDown(self)

    def testDownloadNoUnzip(self):
        main(["download", self.artifact, '--skipunzip'],
             items=[("download", DownloadCommand)])

    def testSimpleDownload(self):
        main(["download", self.artifact],
             items=[("download", DownloadCommand)])

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    unittest.main()
