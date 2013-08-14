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

import os
import unittest

from omego.framework import main
from omego.upgrade import UpgradeCommand


class TestUpgrade(unittest.TestCase):

    def assertUpgrade(self, *args):
        args = ["upgrade"] + list(args)
        main(args=args, items=[("upgrade", UpgradeCommand)])

    def testUpgradeHelp(self):
        try:
            self.assertUpgrade("-h")
        except SystemExit, se:
            self.assertEquals(0, se.code)

    def testUpgradeDryRun(self):
        self.assertUpgrade("-n")

    def testUpgradeDryRunVerbose(self):
        self.assertUpgrade("-n", "-v")

    def testUpgrade(self):
        self.assertUpgrade("--branch=OMERO-trunk-ice34")


if __name__ == '__main__':
    import logging
    logging.basicConfig()
    unittest.main()
