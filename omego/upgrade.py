#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import copy
import os
import shutil
import tempfile
import logging

from artifacts import Artifacts
from db import DbAdmin, DB_UPTODATE, DB_UPGRADE_NEEDED, DB_INIT_NEEDED
from external import External
from yaclifw.framework import Command, Stop
import fileutils
from env import EnvDefault, DbParser, FileUtilsParser, JenkinsParser
from env import WINDOWS

log = logging.getLogger("omego.upgrade")


class Install(object):

    def __init__(self, cmd, args):
        self.args, newinstall = self._handle_args(cmd, args)
        log.info("%s: %s", self.__class__.__name__, cmd)
        log.debug("Current directory: %s", os.getcwd())
        self.symlink_check_and_set()

        if newinstall is None:
            # Automatically install or upgrade
            newinstall = not os.path.exists(args.sym)
        elif newinstall is False:
            if not os.path.exists(args.sym):
                raise Stop(30, 'Symlink is missing: %s' % args.sym)
        elif newinstall is True:
            if os.path.exists(args.sym):
                raise Stop(30, 'Symlink already exists: %s' % args.sym)
        else:
            assert False

        server_dir = self.get_server_dir()

        if newinstall:
            # Create a symlink to simplify the rest of the logic-
            # just need to check if OLD == NEW
            self.symlink(server_dir, args.sym)
            log.info("Installing %s (%s)...", server_dir, args.sym)
        else:
            log.info("Upgrading %s (%s)...", server_dir, args.sym)

        self.external = External(server_dir)
        self.external.setup_omero_cli()

        if not newinstall:
            self.external.setup_previous_omero_env(args.sym, args.savevarsfile)

        # Need lib/python set above
        import path
        self.dir = path.path(server_dir)

        if not newinstall:
            self.stop()
            self.archive_logs()

        copyold = not newinstall and not args.ignoreconfig
        self.configure(copyold, args.prestartfile)
        self.directories()

        self.handle_database()

        self.external.save_env_vars(args.savevarsfile, args.savevars.split())
        self.start()

    def _handle_args(self, cmd, args):
        """
        We need to support deprecated behaviour for now which makes this
        quite complicated

        Current behaviour:
        - install: Installs a new server, existing server causes an error
        - install --upgrade: Installs or upgrades a server
        - install --managedb: Automatically initialise or upgrade the db

        Deprecated:
        - install --upgradedb --initdb: Replaced by install --managedb
        - install --upgradedb: upgrade the db, must exist
        - install --initdb: initialise the db
        - upgrade: Upgrades a server, must already exist
        - upgrade --upgradedb: Automatically upgrade the db

        returns:
        - Modified args object, flag to indicate new/existing/auto install
        """
        if cmd == 'install':
            if args.upgrade:
                # Current behaviour: install or upgrade
                if args.initdb or args.upgradedb:
                    raise Stop(10, (
                        'Deprecated --initdb --upgradedb flags '
                        'are incompatible with --upgrade'))
                newinstall = None
            else:
                # Current behaviour: Server must not exist
                newinstall = True

            if args.managedb:
                # Current behaviour
                if args.initdb or args.upgradedb:
                    raise Stop(10, (
                        'Deprecated --initdb --upgradedb flags '
                        'are incompatible with --managedb'))
                args.initdb = True
                args.upgradedb = True
            else:
                if args.initdb or args.upgradedb:
                    log.warn('--initdb and --upgradedb are deprecated, '
                             'use --managedb')

        elif cmd == 'upgrade':
            # Deprecated behaviour
            log.warn(
                '"omero upgrade" is deprecated, use "omego install --upgrade"')
            cmd = 'install'
            args.upgrade = True
            # Deprecated behaviour: Server must exist
            newinstall = False

        else:
            raise Exception('Unexpected command: %s' % cmd)

        return args, newinstall

    def get_server_dir(self):
        """
        Either downloads and/or unzips the server if necessary
        return: the directory of the unzipped server
        """
        if not self.args.server:
            if self.args.skipunzip:
                raise Stop(0, 'Unzip disabled, exiting')

            log.info('Downloading server')

            # The downloader automatically symlinks the server, however if
            # we are upgrading we want to delay the symlink swap, so this
            # overrides args.sym
            # TODO: Find a nicer way to do this?
            artifact_args = copy.copy(self.args)
            artifact_args.sym = ''
            artifacts = Artifacts(artifact_args)
            server = artifacts.download('server')
        else:
            progress = 0
            if self.args.verbose:
                progress = 20
            ptype, server = fileutils.get_as_local_path(
                self.args.server, self.args.overwrite, progress=progress,
                httpuser=self.args.httpuser,
                httppassword=self.args.httppassword)
            if ptype == 'file':
                if self.args.skipunzip:
                    raise Stop(0, 'Unzip disabled, exiting')
                log.info('Unzipping %s', server)
                server = fileutils.unzip(
                    server, match_dir=True, destdir=self.args.unzipdir)

        log.debug('Server directory: %s', server)
        return server

    def stop(self):
        try:
            log.info("Stopping server")
            self.bin("admin status --nodeonly")
            self.bin("admin stop")
        except Exception as e:
            log.error('Error whilst stopping server: %s', e)

        if not self.args.no_web:
            try:
                log.info("Stopping web")
                self.stopweb()
            except Exception as e:
                log.error('Error whilst stopping web: %s', e)

    def configure(self, copyold, prestartfile):
        def samecontents(a, b):
            # os.path.samefile is not available on Windows
            try:
                return os.path.samefile(a, b)
            except AttributeError:
                with open(a) as fa:
                    with open(b) as fb:
                        return fa.read() == fb.read()

        target = self.dir / "etc" / "grid" / "config.xml"

        if copyold:
            from path import path
            old_grid = path(self.args.sym) / "etc" / "grid"
            old_cfg = old_grid / "config.xml"
            log.info("Copying old configuration from %s", old_cfg)
            if not old_cfg.exists():
                raise Stop(40, 'config.xml not found')
            if target.exists() and samecontents(old_cfg, target):
                # This likely is caused by the symlink being
                # created early on an initial install.
                pass
            else:
                old_cfg.copy(target)
        else:
            if target.exists():
                log.info('Deleting configuration file %s', target)
                target.remove()

        if prestartfile:
            for f in prestartfile:
                log.info('Loading prestart file %s', f)
                ftype, fpath = fileutils.get_as_local_path(f, 'backup')
                if ftype != 'file':
                    raise Stop(50, 'Expected file, found: %s %s' % (
                        ftype, f))
                self.run(['load', fpath])

    def archive_logs(self):
        if self.args.archivelogs:
            logdir = os.path.join(self.args.sym, 'var', 'log')
            archive = self.args.archivelogs
            log.info('Archiving logs to %s', archive)
            fileutils.zip(archive, logdir, os.path.join(self.args.sym, 'var'))
            return archive

    def directories(self):
        if self.samedir(self.dir, self.args.sym):
            log.warn("Upgraded server was the same, not deleting")
            return

        try:
            target = self.readlink(self.args.sym)
            targetzip = target + '.zip'
        except IOError:
            log.error('Unable to get symlink target: %s', self.args.sym)
            target = None
            targetzip = None

        if self.args.delete_old and target:
            try:
                log.info("Deleting %s", target)
                shutil.rmtree(target)
            except OSError as e:
                log.error("Failed to delete %s: %s", target, e)

        if not self.args.keep_old_zip and targetzip:
            try:
                log.info("Deleting %s", targetzip)
                os.unlink(targetzip)
            except OSError as e:
                log.error("Failed to delete %s: %s", targetzip, e)

        self.rmlink(self.args.sym)
        self.symlink(self.dir, self.args.sym)

    def handle_database(self):
        """
        Handle database initialisation and upgrade, taking into account
        command line arguments
        """
        db = DbAdmin(self.dir, None, self.args, self.external)
        status = db.check()
        log.debug('OMERO database upgrade status: %s', status)

        # TODO: When initdb and upgradedb are dropped we can just test
        # managedb, but for backwards compatibility we need to support
        # initdb without upgradedb and vice-versa
        if status == DB_INIT_NEEDED:
            if self.args.initdb:
                log.debug('Initialising OMERO database')
                db.init()
            else:
                log.error('OMERO database not found')
                raise Stop(DB_INIT_NEEDED,
                           'Install/Upgrade failed: OMERO database not found')

        elif status == DB_UPGRADE_NEEDED:
            log.warn('OMERO database exists but is out of date')
            if self.args.upgradedb:
                log.debug('Upgrading OMERO database')
                db.upgrade()
            else:
                raise Stop(
                    DB_UPGRADE_NEEDED,
                    'Pass --managedb or upgrade your OMERO database manually')

        else:
            assert status == DB_UPTODATE

        return status

    def start(self):
        if self.args.no_start:
            log.debug('Not starting OMERO')
            return

        self.run("admin start")
        if not self.args.no_web:
            log.info("Starting web")
            self.startweb()

    def run(self, command):
        """
        Runs a command as if from the command-line
        without the need for using popen or subprocess
        """
        if isinstance(command, basestring):
            command = command.split()
        else:
            command = list(command)
        self.external.omero_cli(command)

    def bin(self, command):
        """
        Runs the omero command-line client with an array of arguments using the
        old environment
        """
        if isinstance(command, basestring):
            command = command.split()
        self.external.omero_bin(command)

    def symlink_check_and_set(self):
        """
        The default symlink was changed from OMERO-CURRENT to OMERO.server.
        If `--sym` was not specified and OMERO-CURRENT exists in the current
        directory stop and warn.
        """
        if self.args.sym == '':
            if os.path.exists('OMERO-CURRENT'):
                log.error('Deprecated OMERO-CURRENT found but --sym not set')
                raise Stop(
                    30, 'The default for --sym has changed to OMERO.server '
                    'but the current directory contains OMERO-CURRENT. '
                    'Either remove OMERO-CURRENT or explicity pass --sym.')
        if self.args.sym in ('', 'auto'):
            self.args.sym = 'OMERO.server'


class UnixInstall(Install):

    def stopweb(self):
        self.bin("web stop")

    def startweb(self):
        self.run("web start")

    def samedir(self, targetdir, link):
        return os.path.samefile(targetdir, link)

    def readlink(self, link):
        return os.path.normpath(os.readlink(link))

    def rmlink(self, link):
        try:
            os.unlink(link)
        except OSError as e:
            log.error("Failed to unlink %s: %s", link, e)
            raise

    def symlink(self, targetdir, link):
        try:
            os.symlink(targetdir, link)
        except OSError as e:
            log.error("Failed to symlink %s to %s: %s", targetdir, link, e)
            raise


class WindowsInstall(Install):

    def stopweb(self):
        log.info("Removing web from IIS")
        self.bin("web iis --remove")
        self.iisreset()

    def startweb(self):
        log.info("Configuring web in IIS")
        self.run("web iis")
        self.iisreset()

    # os.path.samefile doesn't work on Python 2
    # Create a tempfile in one directory and test for it's existence in the
    # other

    def samedir(self, targetdir, link):
        try:
            return os.path.samefile(targetdir, link)
        except AttributeError:
            with tempfile.NamedTemporaryFile(dir=targetdir) as test:
                return os.path.exists(
                    os.path.join(link, os.path.basename(test.name)))

    # Symlinks are a bit more complicated on Windows:
    # - You must have (elevated) administrator privileges
    # - os.symlink doesn't work on Python 2, you must use a win32 call
    # - os.readlink doesn't work on Python 2, and the solution suggested in
    #   http://stackoverflow.com/a/7924557 doesn't work for me.
    #
    # We need to dereference the symlink in order to delete the old server
    # so for now just store it in a text file alongside the symlink.

    def readlink(self, link):
        try:
            return os.path.normpath(os.readlink(link))
        except AttributeError:
            with open('%s.target' % link, 'r') as f:
                return os.path.normpath(f.read())

    def rmlink(self, link):
        """
        """
        if os.path.isdir(link):
            os.rmdir(link)
        else:
            os.unlink(link)

    def symlink(self, targetdir, link):
        """
        """
        try:
            os.symlink(targetdir, link)
        except AttributeError:
            import win32file
            flag = 1 if os.path.isdir(targetdir) else 0
            try:
                win32file.CreateSymbolicLink(link, targetdir, flag)
            except Exception as e:
                log.error(
                    "Failed to symlink %s to %s: %s", targetdir, link, e)
                raise
            with open('%s.target' % link, 'w') as f:
                f.write(targetdir)

    def iisreset(self):
        """
        Calls iisreset
        """
        self.external.run('iisreset', [])


class InstallBaseCommand(Command):
    """
    Base command class to install or upgrade an OMERO server
    Do not call this class directly
    """

    def __init__(self, sub_parsers):
        super(InstallBaseCommand, self).__init__(sub_parsers)

        self.parser.add_argument("-n", "--dry-run", action="store_true")
        self.parser.add_argument(
            "server", nargs="?", help="The server directory, or a server-zip, "
            "or the url of a server-zip")

        self.parser.add_argument(
            "--prestartfile", action="append",
            help="Run these OMERO commands before starting server, "
                 "can be repeated")
        self.parser.add_argument(
            "--ignoreconfig", action="store_true",
            help="Don't copy the old configuration file when upgrading")

        self.parser = JenkinsParser(self.parser)
        self.parser = DbParser(self.parser)
        self.parser = FileUtilsParser(self.parser)

        Add = EnvDefault.add

        self.parser.add_argument(
            "--no-start", action="store_true",
            help="Don't start any omero components")

        self.parser.add_argument(
            "--no-web", action="store_true",
            help="Ignore OMERO.web, don't start or stop")

        self.parser.add_argument(
            "--delete-old", action="store_true",
            help="Delete the old server directory")
        self.parser.add_argument(
            "--keep-old-zip", action="store_true",
            help="Don't delete the old server zip")

        # Record the values of these environment variables in a file
        envvars = "ICE_HOME PATH DYLD_LIBRARY_PATH LD_LIBRARY_PATH PYTHONPATH"
        envvarsfile = os.path.join("%(sym)s", "omero.envvars")
        Add(self.parser, "savevars", envvars)
        Add(self.parser, "savevarsfile", envvarsfile)

    def __call__(self, args):
        super(InstallBaseCommand, self).__call__(args)
        self.configure_logging(args)

        # Since EnvDefault.__action__ is only called if a user actively passes
        # a variable, there's no way to do the string replacing in the action
        # itself. Instead, we're post-processing them here, but this could be
        # improved.

        names = sorted(x.dest for x in self.parser._actions)
        for dest in names:
            if dest in ("help", "verbose", "quiet"):
                continue
            value = getattr(args, dest)
            if value and isinstance(value, basestring):
                replacement = value % dict(args._get_kwargs())
                log.debug("% 20s => %s" % (dest, replacement))
                setattr(args, dest, replacement)

        if args.dry_run:
            return

        if WINDOWS:
            WindowsInstall(self.NAME, args)
        else:
            UnixInstall(self.NAME, args)


class InstallCommand(InstallBaseCommand):
    """
    Setup or upgrade an OMERO installation.
    """
    # TODO: When UpgradeCommand is removed InstallBaseCommand and
    # InstallCommand can be combined

    NAME = "install"

    def __init__(self, sub_parsers):
        super(InstallCommand, self).__init__(sub_parsers)
        group = self.parser.add_argument_group('Database management')
        group.add_argument("--initdb", action="store_true",
                           help=argparse.SUPPRESS)
        group.add_argument("--upgradedb", action="store_true",
                           help=argparse.SUPPRESS)
        self.parser.add_argument(
            "--upgrade", action="store_true",
            help="Upgrade the server if already installed")
        self.parser.add_argument(
            "--managedb", action="store_true",
            help="Initialise or upgrade the database if necessary")
        self.parser.add_argument(
            "--archivelogs", default=None, help=(
                "If a logs directory exists archive to this zip file, "
                "overwriting if it exists"))


class UpgradeCommand(InstallBaseCommand):
    """
    DEPRECATED: Use `omego install --upgrade` instead
    """

    NAME = "upgrade"

    def __init__(self, sub_parsers):
        super(UpgradeCommand, self).__init__(sub_parsers)
        self.parser.add_argument(
            "--upgradedb", action="store_true", help="Upgrade the database")
        self.parser.add_argument(
            "--archivelogs", default=None, help=(
                "Archive the logs directory to this zip file, "
                "overwriting if it exists"))
