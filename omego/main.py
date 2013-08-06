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

from omego.framework import Command

from omego.framework import Stop

from omego.upgrade import *


def main(args=None):
    """
    Reusable entry point. Arguments are parsed
    via the argparse-subcommands configured via
    each Command class found in globals(). Stop
    exceptions are propagated to callers.
    """

    if not argparse_loaded:
        raise Stop(2, "Missing required module")
    if args is None: args = sys.argv[1:]

    omego_parser, sub_parsers = parsers()

    for name, MyCommand in sorted(globals().items()):
        if not isinstance(MyCommand, type): continue
        if not issubclass(MyCommand, Command): continue
        if MyCommand.NAME == "abstract": continue
        MyCommand(sub_parsers)

    ns = omego_parser.parse_args(args)
    ns.func(ns)


def entry_point():
    """
    External entry point which calls main() and
    if Stop is raised, calls sys.exit()
    """
    try:
        main()
    except Stop, stop:
        print stop,
        sys.exit(stop.rc)


if __name__ == "__main__":
    entry_point()
