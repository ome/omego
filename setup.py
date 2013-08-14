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
OME-GO Management library
"""

from distutils.core import setup
from omego.version import get_git_version


DATA_FILES = [('.', ['LICENSE.txt', 'README.rst', 'requirements.txt'])]
ZIP_SAFE = True
try:
    VERSION = get_git_version()
    DATA_FILES[0][1].append("RELEASE-VERSION")
    ZIP_SAFE = False
except:
    VERSION = "0.0.0"  # Non-tagged

LONG_DESCRIPTION = open("README.rst", "r").read()

CLASSIFIERS = ["Development Status :: 4 - Beta",
               "Environment :: Console",
               "Intended Audience :: Developers",
               "Intended Audience :: System Administrators",
               "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
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
      packages = ['omego'],
      install_requires = [],  # Skipping argparse for Python 2.7 and greater.
      entry_points = { 'console_scripts': ['omego = omego.main:entry_point'] },
      data_files = DATA_FILES,
      zip_safe = ZIP_SAFE,

      # Using global variables
      long_description=LONG_DESCRIPTION,
      classifiers=CLASSIFIERS,
      version=VERSION,
      )
