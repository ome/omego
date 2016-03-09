#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import logging
import os
import sys
import tempfile
import time

from env import WINDOWS

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


class External(object):
    """
    Manages the execution of shell and OMERO CLI commands
    """

    def __init__(self, dir=None):
        self.old_env = None
        self.cli = None
        self.configured = None

        self.dir = None
        if dir:
            self.set_server_dir(dir)

        self._omero = None

    def set_server_dir(self, dir):
        """
        Set the directory of the server to be controlled
        """
        self.dir = os.path.abspath(dir)
        config = os.path.join(self.dir, 'etc', 'grid', 'config.xml')
        self.configured = os.path.exists(config)

    def has_config(self):
        """
        Checks whether a config.xml file existed in the new server when the
        directory was first set by set_server_dir(). Importing omero.cli
        may automatically create an empty file, so we have to use the saved
        state.
        """
        if not self.dir:
            raise Exception('No server directory set')
        return self.configured

    def get_config(self, force=False):
        """
        Returns a dictionary of all config.xml properties

        If `force = True` then ignore any cached state and read config.xml
        if possible

        setup_omero_cli() must be called before this method to import the
        correct omero module to minimise the possibility of version conflicts
        """
        if not force and not self.has_config():
            raise Exception('No config file')

        configxml = os.path.join(self.dir, 'etc', 'grid', 'config.xml')
        if not os.path.exists(configxml):
            raise Exception('No config file')

        try:
            # Attempt to open config.xml read-only, though this flag is not
            # present in early versions of OMERO 5.0
            c = self._omero.config.ConfigXml(
                configxml, exclusive=False, read_only=True)
        except TypeError:
            c = self._omero.config.ConfigXml(configxml, exclusive=False)

        try:
            return c.as_map()
        finally:
            c.close()

    def setup_omero_cli(self):
        """
        Imports the omero CLI module so that commands can be run directly.
        Note Python does not allow a module to be imported multiple times,
        so this will only work with a single omero instance.

        This can have several surprising effects, so setup_omero_cli()
        must be explcitly called.
        """
        if not self.dir:
            raise Exception('No server directory set')

        if 'omero.cli' in sys.modules:
            raise Exception('omero.cli can only be imported once')

        log.debug("Setting up omero CLI")
        lib = os.path.join(self.dir, "lib", "python")
        if not os.path.exists(lib):
            raise Exception("%s does not exist!" % lib)
        sys.path.insert(0, lib)

        import omero
        import omero.cli

        log.debug("Using omero CLI from %s", omero.cli.__file__)

        self.cli = omero.cli.CLI()
        self.cli.loadplugins()
        self._omero = omero

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
        self.run('omero', command, capturestd=True, env=self.old_env)

    @staticmethod
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
