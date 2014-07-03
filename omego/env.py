#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from yaclifw import argparseconfig
from yaclifw.framework import Command
import platform
import subprocess


class OmegoCommand(Command):
    """
    Base class for omego commands
    Includes main in the list config file sections to be merged
    """

    def __init__(self, sub_parsers, parents):
        super(OmegoCommand, self).__init__(
            sub_parsers, parents, ['main', self.NAME])


###########################################################################
# DETECTION
###########################################################################

WINDOWS = platform.system() == "Windows"
p = subprocess.Popen(["hostname"], stdout=subprocess.PIPE)
HOSTNAME = p.communicate()[0].strip()
del p

IS_JENKINS_JOB = all([key in os.environ for key in
                      ["JOB_NAME", "BUILD_NUMBER", "BUILD_URL"]])
if IS_JENKINS_JOB:
    # Set BUILD_ID to DONT_KILL_ME to avoid server shutdown at job termination
    os.environ["BUILD_ID"] = "DONT_KILL_ME"


###########################################################################
# ArgParse classes
###########################################################################


def Add(parser, name, default, **kwargs):
    parser.add_argument("--%s" % name, default=default, **kwargs)


class DbParser(argparseconfig.ArgparseConfigParser):

    def __init__(self, parser):
        self.parser = parser
        group = self.parser.add_argument_group(
            'Database arguments',
            'Arguments related to administering the database')

        Add(group, "dbhost", HOSTNAME,
            help="Hostname of the OMERO database server")
        # No default dbname to prevent inadvertent upgrading of databases
        Add(group, "dbname", None,
            help="Name of the OMERO database")
        Add(group, "dbuser", "omero",
            help="Username for connecting to the OMERO database")
        Add(group, "dbpass", "omero",
            help="Password for connecting to the OMERO database")
        # TODO Admin credentials: dbauser, dbapass

        Add(group, "omerosql", "omero.sql",
            help="OMERO database SQL file")
        Add(group, "rootpass", "omero",
            help="OMERO admin password")

    def __getattr__(self, key):
        return getattr(self.parser, key)


class JenkinsParser(argparseconfig.ArgparseConfigParser):

    def __init__(self, parser):
        self.parser = parser
        group = self.parser.add_argument_group(
            'Jenkins arguments',
            'Arguments related to the Jenkins instance')

        Add(group, "ci", "ci.openmicroscopy.org",
            help="Base url of the continuous integration server")
        Add(group, "branch", "OMERO-5.0-latest",
            help="Name of the Jenkins job containing the artifacts")
        Add(group, "build",
            "http://%(ci)s/job/%(branch)s/lastSuccessfulBuild/",
            help="Full url of the Jenkins build containing the artifacts")
        Add(group, "labels", "ICE=3.5",
            help="Comma separated list of labels for matrix builds")

    def __getattr__(self, key):
        return getattr(self.parser, key)


class FileUtilsParser(argparseconfig.ArgparseConfigParser):

    def __init__(self, parser):
        self.parser = parser
        group = self.parser.add_argument_group(
            'Remote and local file handling parameters',
            'Additional arguments for downloading or unzipped files')

        Add(group, "unzipdir", "",
            help="Unzip archives into this directory")
        group.add_argument("--skipunzip", action="store_true",
                           help="Don't unzip archives")
        # Choices from fileutils.get_as_local_path
        Add(group, "overwrite", "keep",
            choices=["error", "backup", "keep"],
            help="Whether to overwrite or keep existing files (default error)")

        Add(group, "httpuser", None,
            help="Username for HTTP authentication")
        Add(group, "httppassword", None,
            help="Password for HTTP authentication")

    def __getattr__(self, key):
        return getattr(self.parser, key)
