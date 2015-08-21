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

"""
Primary launching functions for omego. All Commands
which are present in the globals() of this module
will be presented to the user.
"""

import sys

from yaclifw.framework import main, Stop

from artifacts import DownloadCommand
from convert import ConvertCommand
from db import DbCommand
from upgrade import InstallCommand
from upgrade import UpgradeCommand
from version import Version


def entry_point():
    """
    External entry point which calls main() and
    if Stop is raised, calls sys.exit()
    """
    try:
        main("omego", items=[
            (InstallCommand.NAME, InstallCommand),
            (UpgradeCommand.NAME, UpgradeCommand),
            (ConvertCommand.NAME, ConvertCommand),
            (DownloadCommand.NAME, DownloadCommand),
            (DbCommand.NAME, DbCommand),
            (Version.NAME, Version)])
    except Stop, stop:
        if stop.rc != 0:
            print "ERROR:", stop
        else:
            print stop
        sys.exit(stop.rc)


if __name__ == "__main__":
    entry_point()
