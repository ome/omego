#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import logging
import os
import sys

log = logging.getLogger("omego.external")


class RunException(Exception):

    def __init__(self, msg, exe, exeargs, r, stdout, stderr):
        super(RunException, self).__init__(msg)
        self.exe = exe
        self.exeargs = exeargs
        self.r = r
        self.stdout = stdout
        self.stderr = stderr

    def fullstr(self):
        return '%s\nstdout: %s\nstderr: %s' % (
            self.__str__(), self.stdout, self.stderr)

    def __str__(self):
        return '%s\ncommand: %s %s\nreturn code: %d' % (
            super(RunException, self).__str__(), self.exe,
            ' '.join(self.exeargs), self.r)


class External(object):
    """
    Manages the execution of shell and OMERO CLI commands
    """

    def __init__(self):
        self.old_env = None
        self.cli = None

    def setup_omero_cli(self, dir):
        """
        Imports the omero CLI module so that commands can be run directly.
        Note Python does not allow a module to be imported multiple times,
        so this will only work with a single omero instance.

        This can have several surprisingly effects, so setup_omero_cli()
        must be explcitly called.
        """
        if 'omero.cli' in sys.modules:
            raise Exception('omero.cli can only be imported once')

        log.debug("Setting up omero CLI")
        dir = os.path.abspath(dir)
        lib = os.path.join(dir, "lib", "python")
        if not os.path.exists(lib):
            raise Exception("%s does not exist!" % lib)
        sys.path.insert(0, lib)

        import omero
        import omero.cli

        log.debug("Using omero CLI from %s", omero.cli.__file__)

        self.cli = omero.cli.CLI()
        self.cli.loadplugins()

    def setup_previous_omero_env(self, olddir, savevarsfile):
        """
        Create a copy of the current environment for interacting with the
        current OMERO server installation
        """
        env = self.get_environment(savevarsfile)

        def addpath(varname, p):
            if not os.path.exists(p):
                raise Exception("%s does not exist!" % p)
            current = env.get(varname)
            if current:
                env[varname] = p + os.pathsep + current
            else:
                env[varname] = p

        olddir = os.path.abspath(olddir)
        lib = os.path.join(olddir, "lib", "python")
        addpath("PYTHONPATH", lib)
        bin = os.path.join(olddir, "bin")
        addpath("PATH", bin)
        self.old_env = env

    def omero_cli(self, command):
        """
        Runs a command as if from the OMERO command-line without the need
        for using popen or subprocess.
        """
        assert isinstance(command, list)
        if not self.cli:
            raise Exception('omero.cli not initialised')
        log.info("Invoking CLI [current environment]: %s", " ".join(command))
        self.cli.invoke(command, strict=True)

    def omero_bin(self, command):
        """
        Runs the omero command-line client with an array of arguments using the
        old environment
        """
        assert isinstance(command, list)
        if not self.old_env:
            raise Exception('Old environment not initialised')
        log.info("Running [old environment]: %s", " ".join(command))
        self.run('omero', command, self.old_env)

    @staticmethod
    def run(exe, args, env=None):
        """
        Runs an executable with an array of arguments, optionally in the
        specified environment.
        Returns stdout and stderr
        """
        command = [exe] + args
        if env:
            log.info("Executing [custom environment]: %s", " ".join(command))
        else:
            log.info("Executing : %s", " ".join(command))
        proc = subprocess.Popen(
            command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Use communicate() since wait() may deadlock
        stdout, stderr = proc.communicate()
        r = proc.returncode

        if r != 0:
            raise RunException(
                "Non-zero return code", exe, args, r, stdout, stderr)
        return stdout, stderr

    def get_environment(self, filename=None):
        env = os.environ.copy()
        if not filename:
            log.debug("Using original environment")
            return env

        try:
            with open(filename, "r") as f:
                log.info("Loading old environment")
                for line in f:
                    key, value = line.strip().split("=", 1)
                    env[key] = value
                    log.debug("  %s=%s", key, value)
        except IOError as e:
            log.error("Failed to load environment variables from %s: %s",
                      filename, e)

        # TODO: Throw a catchable exception
        return env

    def save_env_vars(self, filename, varnames):
        try:
            with open(filename, "w") as f:
                log.info("Saving environment")
                for var in varnames:
                    value = os.environ.get(var, "")
                    f.write("%s=%s\n" % (var, value))
                    log.debug("  %s=%s", var, value)
        except IOError as e:
            log.error("Failed to save environment variables to %s: %s",
                      filename, e)
