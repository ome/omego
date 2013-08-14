#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
import platform
import subprocess


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


_so_url = ("http://stackoverflow.com/questions",
           "/10551117/setting-options-from-environment",
           "-variables-when-using-argparse")


class EnvDefault(argparse.Action):
    """
    argparse Action which can be used to also read values
    from the current environment. Additionally, it will
    replace any values in string replacement syntax that
    have already been set in the environment (e.g. %%(prefix)4064
    becomes 14064 if --prefix=1 was set)

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
