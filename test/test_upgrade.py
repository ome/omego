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

import pytest

from omego.framework import main, Stop
from omego.upgrade import UpgradeCommand


class TestUpgrade(object):

    def upgrade(self, *args):
        args = ["upgrade"] + list(args)
        main(args=args, items=[("upgrade", UpgradeCommand)])

    def testUpgradeHelp(self):
        try:
            self.upgrade("-h")
        except SystemExit, se:
            assert se.code == 0

    def testUpgradeDryRun(self):
        self.upgrade("-n")

    def testUpgradeDryRunVerbose(self):
        self.upgrade("-n", "-v")

    def testSkipunzip(self):
        with pytest.raises(Stop):
            self.upgrade("--skipunzip")

    def testUpgrade(self):
        self.upgrade("--unzipargs=-q", "--branch=OMERO-5.0-latest-ice34")

    @pytest.mark.skipif(True, reason='Broken due to multiple CLI import')
    def testUpgradeMatrixBuild(self):
        self.upgrade(
            "--unzipargs=-q", "--branch=OMERO-5.1-latest", "--labels=ICE=3.4")
