#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from builtins import object
import subprocess
import logging
import os
import tempfile
import time

from .env import WINDOWS

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
            self.shortstr(), self.stdout, self.stderr)

    def shortstr(self):
        return '%s\ncommand: %s %s\nreturn code: %d' % (
            super(RunException, self).__str__(), self.exe,
            ' '.join(self.exeargs), self.r)

    def __str__(self):
        return self.fullstr()


def run(exe, args, capturestd=False, env=None):
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
    start = time.time()

    # Temp files will be automatically deleted on close()
    # If run() throws the garbage collector should call close(), so don't
    # bother with try-finally
    outfile = None
    errfile = None
    if capturestd:
        outfile = tempfile.TemporaryFile()
        errfile = tempfile.TemporaryFile()

    # Use call instead of Popen so that stdin is connected to the console,
    # in case user input is required
    # On Windows shell=True is needed otherwise the modified environment
    # PATH variable is ignored. On Unix this breaks things.
    r = subprocess.call(
        command, env=env, stdout=outfile, stderr=errfile, shell=WINDOWS)

    stdout = None
    stderr = None
    if capturestd:
        outfile.seek(0)
        stdout = outfile.read()
        outfile.close()
        errfile.seek(0)
        stderr = errfile.read()
        errfile.close()

    end = time.time()
    if r != 0:
        log.error("Failed [%.3f s]", end - start)
        raise RunException(
            "Non-zero return code", exe, args, r, stdout, stderr)
    log.info("Completed [%.3f s]", end - start)
    return stdout, stderr


class External(object):
    """
    Manages the execution of shell and OMERO CLI commands
    """

    def __init__(self, dir, python):
        self.old_env = None
        self.cli = None
        self.python = python

        self.dir = None
        if dir:
            self.set_server_dir(dir)

        self._omero = None

    def set_server_dir(self, dir):
        """
        Set the directory of the server to be controlled
        """
        self.dir = os.path.abspath(dir)

    def get_config(self):
        """
        Returns a dictionary of all OMERO config properties

        Assumes properties are in the form key=value, multiline-properties are
        not supported
        """
        stdout, stderr = self.omero_cli(['config', 'get'])
        try:
            return dict(line.split('=', 1)
                        for line in stdout.decode().splitlines() if line)
        except ValueError:
            raise Exception('Failed to parse omero config: %s' % stdout)

    def setup_omero_cli(self, omero_cli=None):
        """
        Configures the OMERO CLI.
        omero_cli: path to bin/omero command, if None then try in order:
        - OMERO.server/bin/omero
        - omero (in PATH)
        """
        if not omero_cli:
            if self.dir:
                omero_bin = os.path.join(self.dir, "bin", "omero")
                if (os.path.exists(omero_bin) and
                        self._bin_omero_valid(omero_bin)):
                    omero_cli = omero_bin
            if not omero_cli:
                omero_bin = 'omero'
                if self._bin_omero_valid(omero_bin):
                    omero_cli = omero_bin
            if not omero_cli:
                raise Exception('Unable to find omero executable')
        else:
            if not self._bin_omero_valid(omero_cli):
                raise Exception('Unable to execute omero executable')

        log.debug("Using omero CLI from %s", omero_cli)
        self.cli = omero_cli

    def _bin_omero_valid(self, bin_omero):
        try:
            self.run_python(bin_omero, ['version'])
            return True
        except RunException:
            return False

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
        self.old_cli = os.path.join(bin, "omero")

    def omero_cli(self, command):
        """
        Runs an OMERO CLI command
        CLI must have been initialised using setup_omero_cli()
        """
        assert isinstance(command, list)
        if not self.cli:
            raise Exception('OMERO CLI not initialised')
        return self.run_python(self.cli, command, capturestd=True)

    def omero_old(self, command):
        """
        Runs the omero command-line client with an array of arguments using the
        old environment
        """
        assert isinstance(command, list)
        if not self.old_env:
            raise Exception('Old environment not initialised')
        log.info("Running [old environment]: %s %s",
                 self.old_cli, " ".join(command))
        return self.run_python(
            self.old_cli, command, capturestd=True, env=self.old_env)

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

    def run_python(self, command, args, **kwargs):
        return run(self.python, [command] + args, **kwargs)
