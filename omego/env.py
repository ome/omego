#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
import platform


###########################################################################
# DETECTION
###########################################################################

WINDOWS = platform.system() == "Windows"
IS_JENKINS_JOB = all([key in os.environ for key in
                      ["JOB_NAME", "BUILD_NUMBER", "BUILD_URL"]])
if IS_JENKINS_JOB:
    # Set BUILD_ID to DONT_KILL_ME to avoid server shutdown at job termination
    os.environ["BUILD_ID"] = "DONT_KILL_ME"


###########################################################################
# ArgParse classes
###########################################################################


_so_url = ("http://stackoverflow.com/questions",
           "/10551117/setting-options-from-environment",
           "-variables-when-using-argparse")


class EnvDefault(argparse.Action):
    """
    argparse Action which can be used to also read values
    from the current environment. Additionally, it will
    replace any values in string replacement syntax that
    have already been set in the environment (e.g. %%(xxx)234
    becomes 1234 if --xxx=1 was set)

    Usage:

    parser.add_argument(
        "-u", "--url", action=EnvDefault, envvar='URL',
        help="...")

    See: %s

    Note: required set to False rather than True to handle
    empty string defaults.

    """ % (_so_url,)

    def __init__(self, envvar, required=False, default=None, **kwargs):
        if not default and envvar:
            if envvar in os.environ:
                default = envvar
        if required and default:
            required = False
        super(EnvDefault, self).__init__(default=default,
                                         required=required,
                                         **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

    @classmethod
    def add(kls, parser, name, default, **kwargs):
        parser.add_argument("--%s" % name, action=kls, envvar=name.upper(),
                            default=default, **kwargs)


class DbParser(argparse.ArgumentParser):

    def __init__(self, parser):
        self.parser = parser
        group = self.parser.add_argument_group(
            'Database arguments',
            'Arguments related to administering the database')

        Add = EnvDefault.add
        Add(group, "dbhost", 'localhost',
            help="Hostname of the OMERO database server")
        # No default dbname to prevent inadvertent upgrading of databases
        Add(group, "dbname", None,
            help="Name of the OMERO database")
        Add(group, "dbuser", "omero",
            help="Username for connecting to the OMERO database")
        Add(group, "dbpass", "omero",
            help="Password for connecting to the OMERO database")
        group.add_argument(
            "--no-db-config", action="store_true",
            help="Ignore the database settings in omero config")
        # TODO Admin credentials: dbauser, dbapass

        Add(group, "omerosql", None,
            help="OMERO database SQL initialisation file")
        Add(group, "rootpass", "omero",
            help="OMERO admin password")

    def __getattr__(self, key):
        return getattr(self.parser, key)


class JenkinsParser(argparse.ArgumentParser):

    def __init__(self, parser):
        self.parser = parser
        group = self.parser.add_argument_group(
            'Download arguments',
            'Arguments related to the Continuous Integration server or'
            ' the downloads server.')

        Add = EnvDefault.add
        Add(group, "ci", "ci.openmicroscopy.org",
            help="Base URL of the Continuous Integration server (CI only)")
        group.add_argument(
            "--branch", "--release", default="latest",
            help="The release series to download e.g. 5, 5.1, 5.1.2, "
            "use 'latest' to get the latest release. "
            "Alternatively the name of a Jenkins job e.g. OMERO-5.1-latest.")
        Add(group, "build", "",
            help="Full url of the Jenkins build containing the artifacts (CI"
            " only)")
        Add(group, "labels", "",
            help="Comma separated list of labels for matrix builds (CI only)")

        Add(group, "downloadurl",
            "https://downloads.openmicroscopy.org",
            help="Base URL of the downloads server. Since 0.6.0, the OMERO"
            " artifacts are expected to be found under "
            " DOWNLOADURL/omero/<version>/artifacts. Default: "
            "http://downloads.openmicroscopy.org")

        Add(group, "ice",
            "", help="Ice version, default is the latest (release only)")

        Add(group, "sym", "",
            help="Create a symlink to the unzipped download, "
            "replaces any existing symlink. "
            "Use 'auto' to automatically name the symlink OMERO.$component.")

    def __getattr__(self, key):
        return getattr(self.parser, key)


class FileUtilsParser(argparse.ArgumentParser):

    def __init__(self, parser):
        self.parser = parser
        group = self.parser.add_argument_group(
            'Remote and local file handling parameters',
            'Additional arguments for downloading or unzipped files')

        Add = EnvDefault.add
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
