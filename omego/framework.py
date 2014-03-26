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
Framework copied from openmicroscopy/snoopycrimecop for
registering commands.

See the documentation on each Command subclass for specifics.

Environment variables:
    OMEGO_DEBUG_LEVEL     default: logging.INFO

"""

import os
import sys
import logging

argparse_loaded = True
try:
    import argparse
except ImportError:
    print >> sys.stderr, \
        "Module argparse missing. Install via 'pip install argparse'"
    argparse_loaded = False


OMEGO_DEBUG_LEVEL = logging.INFO
if "OMEGO_DEBUG_LEVEL" in os.environ:
    try:
        OMEGO_DEBUG_LEVEL = int(os.environ.get("OMEGO_DEBUG_LEVEL"))
    except:
        OMEGO_DEBUG_LEVEL = 10  # Assume poorly formatted means "debug"


#
# Exceptions
#

class Stop(Exception):
    """
    Exception which specifies that the current execution has finished.
    This is useful when an appropriate user error message has been
    printed and it's not necessary to print a full stacktrace.
    """

    def __init__(self, rc, *args, **kwargs):
        self.rc = rc
        super(Stop, self).__init__(*args, **kwargs)


#
# What follows are the commands which are available from the command-line.
# Alphabetically listed please.
#

class Command(object):
    """
    Base type. At the moment just a marker class which
    signifies that a subclass is a CLI command. Subclasses
    should register themselves with the parser during
    instantiation. Note: Command.__call__ implementations
    are responsible for calling cleanup()
    """

    NAME = "abstract"

    def __init__(self, sub_parsers):
        self.log = logging.getLogger("omego.%s" % self.NAME)
        self.log_level = OMEGO_DEBUG_LEVEL

        help = self.__doc__.lstrip()
        self.parser = sub_parsers.add_parser(self.NAME,
                                             help=help, description=help)
        self.parser.set_defaults(func=self.__call__)

        self.parser.add_argument(
            "-v", "--verbose", action="count", default=0, help=
            "Increase the logging level by multiples of 10")
        self.parser.add_argument(
            "-q", "--quiet", action="count", default=0, help=
            "Decrease the logging level by multiples of 10")

    def __call__(self, args):
        self.configure_logging(args)
        self.cwd = os.path.abspath(os.getcwd())

    def configure_logging(self, args):
        self.log_level += args.quiet * 10
        self.log_level -= args.verbose * 10

        format = "%(asctime)s [%(name)12.12s] %(levelname)-5.5s %(message)s"
        logging.basicConfig(level=self.log_level, format=format)
        logging.getLogger('github').setLevel(logging.INFO)

        self.log = logging.getLogger('omego.%s' % self.NAME)
        self.dbg = self.log.debug


def parsers():

    class HelpFormatter(argparse.RawTextHelpFormatter):
        """
        argparse.HelpFormatter subclass which cleans up our usage,
        preventing very long lines in subcommands.

        Borrowed from omero/cli.py
        Defined inside of parsers() in case argparse is not installed.
        """

        def __init__(self, prog, indent_increment=2, max_help_position=40,
                     width=None):

            argparse.RawTextHelpFormatter.__init__(
                self, prog, indent_increment, max_help_position, width)

            self._action_max_length = 20

        def _split_lines(self, text, width):
            return [text.splitlines()[0]]

        class _Section(argparse.RawTextHelpFormatter._Section):

            def __init__(self, formatter, parent, heading=None):
                # if heading:
                #    heading = "\n%s\n%s" % ("=" * 40, heading)
                argparse.RawTextHelpFormatter._Section.__init__(
                    self, formatter, parent, heading)

    omego_parser = argparse.ArgumentParser(
        description='omego - installation and administration tool',
        formatter_class=HelpFormatter)
    sub_parsers = omego_parser.add_subparsers(title="Subcommands")

    return omego_parser, sub_parsers


def main(args=None, items=None):
    """
    Reusable entry point. Arguments are parsed
    via the argparse-subcommands configured via
    each Command class found in globals(). Stop
    exceptions are propagated to callers.
    """

    if not argparse_loaded:
        raise Stop(2, "Missing required module")

    if args is None:
        args = sys.argv[1:]

    if items is None:
        items = globals().items()

    omego_parser, sub_parsers = parsers()

    for name, MyCommand in sorted(items):
        if not isinstance(MyCommand, type):
            continue
        if not issubclass(MyCommand, Command):
            continue
        if MyCommand.NAME == "abstract":
            continue
        MyCommand(sub_parsers)

    ns = omego_parser.parse_args(args)
    ns.func(ns)
