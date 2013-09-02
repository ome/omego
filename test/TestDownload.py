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

from omego.framework import main
from omego.artifacts import DownloadCommand


class TestDownload(unittest.TestCase):

    def assertDownload(self):
        main(["download", self.artifact, '--skipunzip'],
             items=[("download", DownloadCommand)])

    def testDownloadServer(self):
        self.artifact = 'server'
        self.assertDownload()

    def testDownloadSource(self):
        self.artifact = 'source'
        self.assertDownload()

    def testDownloadWinClients(self):
        self.artifact = 'win'
        self.assertDownload()

    def testDownloadLinuxClients(self):
        self.artifact = 'linux'
        self.assertDownload()

    def testDownloadMacClients(self):
        self.artifact = 'mac'
        self.assertDownload()

    def testDownloadMatlab(self):
        self.artifact = 'matlab'
        self.assertDownload()

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    unittest.main()
