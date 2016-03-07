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

"""
OME-GO Management library
"""

from setuptools import setup
from setuptools.command.test import test as TestCommand

import sys


class PyTest(TestCommand):
    user_options = [
        ('test-path=', 't', "base dir for test collection"),
        ('test-pythonpath=', 'p', "prepend 'pythonpath' to PYTHONPATH"),
        ('test-string=', 'k', "only run tests including 'string'"),
        ('test-marker=', 'm', "only run tests including 'marker'"),
        ('test-no-capture', 's', "don't suppress test output"),
        ('test-failfast', 'x', "Exit on first error"),
        ('test-verbose', 'v', "more verbose output"),
        ('test-quiet', 'q', "less verbose output"),
        ('junitxml=', None, "create junit-xml style report file at 'path'"),
        ('pdb', None, "fallback to pdb on error"),
        ]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.test_pythonpath = None
        self.test_string = None
        self.test_marker = None
        self.test_path = 'test'
        self.test_failfast = False
        self.test_quiet = False
        self.test_verbose = False
        self.test_no_capture = False
        self.junitxml = None
        self.pdb = False

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = [self.test_path]
        if self.test_string is not None:
            self.test_args.extend(['-k', self.test_string])
        if self.test_marker is not None:
            self.test_args.extend(['-m', self.test_marker])
        if self.test_failfast:
            self.test_args.extend(['-x'])
        if self.test_verbose:
            self.test_args.extend(['-v'])
        if self.test_quiet:
            self.test_args.extend(['-q'])
        if self.junitxml is not None:
            self.test_args.extend(['--junitxml', self.junitxml])
        if self.pdb:
            self.test_args.extend(['--pdb'])
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


try:
    from yaclifw.version import get_git_version
    from omego import __file__ as module_file
    VERSION = get_git_version(module_file)
except ImportError:
    VERSION = "UNKNOWN"
ZIP_SAFE = False


LONG_DESCRIPTION = open("README.rst", "r").read()

CLASSIFIERS = ["Development Status :: 4 - Beta",
               "Environment :: Console",
               "Intended Audience :: Developers",
               "Intended Audience :: System Administrators",
               "License :: OSI Approved :: GNU General Public License v2"
               " (GPLv2)",
               "Operating System :: OS Independent",
               "Programming Language :: Python",
               "Topic :: Database :: Database Engines/Servers",
               "Topic :: System :: Software Distribution",
               "Topic :: System :: Systems Administration",
               "Topic :: Utilities"]

setup(name='omego',

      # Simple strings
      author='The Open Microscopy Team',
      author_email='ome-devel@lists.openmicroscopy.org.uk',
      description='OME installation and administration tool',
      license='GPLv2',
      url='https://github.com/ome/omego',

      # More complex variables
      packages=['omego'],
      include_package_data=True,
      entry_points={'console_scripts': ['omego = omego.main:entry_point']},
      zip_safe=ZIP_SAFE,
      # REQUIREMENTS:
      # These should be kept in sync with requirements.txt
      # Skipping argparse for Python 2.7 and greater.
      install_requires=['yaclifw>=0.1.1'],

      # Using global variables
      long_description=LONG_DESCRIPTION,
      classifiers=CLASSIFIERS,
      version=VERSION,

      cmdclass={'test': PyTest},
      tests_require=['pytest', 'restview', 'mox'],
      )
