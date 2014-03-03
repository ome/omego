# -*- coding: utf-8 -*-
# Author: Douglas Creager <dcreager@dcreager.net>
# This file is placed into the public domain.

# Calculates the current version number.  If possible, this is the
# output of “git describe”, modified to conform to the versioning
# scheme that setuptools uses.  If “git describe” returns an error
# (most likely because we're in an unpacked copy of a release tarball,
# rather than in a git working copy), then we fall back on reading the
# contents of the RELEASE-VERSION file.
#
# To use this script, simply import it your setup.py file, and use the
# results of get_git_version() as your package version:
#
# from version import *
#
# setup(
#     version=get_git_version(),
#     .
#     .
#     .
# )
#
# This will automatically update the RELEASE-VERSION file, if
# necessary.  Note that the RELEASE-VERSION file should *not* be
# checked into git; please add it to your top-level .gitignore file.
#
# You'll probably want to distribute the RELEASE-VERSION file in your
# sdist tarballs; to do this, just create a MANIFEST.in file that
# contains the following line:
#
#   include RELEASE-VERSION

__all__ = ("get_git_version")

from subprocess import Popen, PIPE
from os import path, getcwd, chdir
from framework import Command
import re

version_dir = path.abspath(path.dirname(__file__))
version_file = path.join(version_dir, "RELEASE-VERSION")


def call_git_describe(abbrev=4):
    try:
        p = Popen(['git', 'describe', '--match=[v0-9][.0-9]*',
                   '--abbrev=%d' % abbrev], stdout=PIPE, stderr=PIPE)
        p.stderr.close()
        line = p.stdout.readlines()[0]
        return line.strip()

    except:
        return None


def read_release_version():
    try:
        with open(version_file, "r") as f:
            version = f.readlines()[0]
            return version.strip()
    except:
        return None


def write_release_version(version):
    with open(version_file, "w") as f:
        f.write("%s\n" % version)

version_pattern = '^(v)?(?P<version>[0-9]+[\.][0-9]+[\.][0-9]+(\-.+)*)$'
version_pattern = re.compile(version_pattern)


def get_git_version(abbrev=4):
    # Read in the version that's currently in RELEASE-VERSION.
    release_version = read_release_version()

    # First try to get the current version using “git describe”.
    cwd = getcwd()
    git_version = None
    try:
        chdir(version_dir)
        git_version = call_git_describe(abbrev)
    finally:
        chdir(cwd)

    # Extract version number
    version = None
    if git_version:
        m = version_pattern.match(git_version)
        if m:
            version = m.group('version')

    # If that doesn't work, fall back on the value that's in
    # RELEASE-VERSION.

    if version is None:
        version = release_version

    # If we still don't have anything, that's an error.

    if version is None:
        raise ValueError("Cannot find the version number!")

    # If the current version is different from what's in the
    # RELEASE-VERSION file, update the file to be current.

    if version != release_version:
        write_release_version(version)

    # Finally, return the current version.

    return version


class Version(Command):
    """Find which version of omego is being used"""

    NAME = "version"

    def __init__(self, sub_parsers):
        super(Version, self).__init__(sub_parsers)
        # No token args

    def __call__(self, args):
        super(Version, self).__call__(args)

        try:
            version = get_git_version()
        except:
            version = "unknown"
        print version

if __name__ == "__main__":
    print get_git_version()
