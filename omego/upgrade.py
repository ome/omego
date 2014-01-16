#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import logging

import fileinput
import smtplib

from artifacts import Artifacts
from db import DbAdmin
from external import External
from framework import Command, Stop
from env import EnvDefault, DbParser, JenkinsParser
from env import WINDOWS
from env import HOSTNAME

log = logging.getLogger("omego.upgrade")


class Email(object):

    def __init__(self, artifacts, args):

        TO = args.recipients
        FROM = args.sender
        text = "The OMERO.server on %s has been upgraded. \n" \
               "=========================\n" \
               "THIS SERVER REQUIRES VPN!\n" \
               "=========================\n" \
               "Please download suitable clients from: \n " \
               "\n - Windows: \n %s\n " \
               "\n - MAC: \n %s\n " \
               "\n - Linux: \n %s\n " \
               "\n - Webclient available on %s. \n \n " %\
               (args.server, artifacts.win, artifacts.mac,
                artifacts.linux, args.weburl)
        BODY = "\r\n".join(("From: %s" % FROM,
                            "To: %s" % TO,
                            "Subject: %s" % args.subject,
                            "",
                            text))
        server = smtplib.SMTP(args.smtp_server)
        server.sendmail(FROM, args.recipients, BODY)
        server.quit()

        log.info("Mail was sent to: %s", args.recipients)


class Upgrade(object):

    def __init__(self, dir, args):

        self.dir = dir
        self.args = args
        log.info("%s: Upgrading %s (%s)...",
                 self.__class__.__name__, dir, args.sym)

        # setup_script_environment() may cause the creation of a default
        # config.xml, so we must check for it here
        noconfigure = self.has_config(dir)

        # If the symlink doesn't exist, create
        # it which simplifies the rest of the logic,
        # which already checks if OLD === NEW
        if not os.path.exists(args.sym):
            self.mklink(self.dir)

        self.external = External()
        self.external.setup_omero_cli(dir)
        self.external.setup_previous_omero_env(args.sym, args.savevarsfile)

        # Need lib/python set above
        import path
        self.cfg = path.path(args.cfg)
        self.dir = path.path(dir)

        self.stop()

        self.configure(noconfigure)
        self.directories()

        self.upgrade_db()

        self.external.save_env_vars(args.savevarsfile, args.savevars.split())
        self.start()

    def stop(self):
        try:
            log.info("Stopping server")
            self.bin("admin status --nodeonly")
            self.bin("admin stop")
        except Exception as e:
            log.error('Error whilst stopping server: %s', e)

        if self.web():
            log.info("Stopping web")
            self.stopweb()

    def has_config(self, dir):
        config = os.path.join(dir, "etc", "grid", "config.xml")
        return os.path.exists(config)

    def configure(self, noconfigure):

        target = self.dir / "etc" / "grid" / "config.xml"
        if noconfigure:
            log.warn("Target %s already exists, skipping.", target)
            self.configure_ports()
            return  # Early exit!

        if not self.cfg.exists():
            log.info("%s not found. Copying old files", self.cfg)
            from path import path
            old_grid = path(self.args.sym) / "etc" / "grid"
            old_cfg = old_grid / "config.xml"
            if target.exists() and os.path.samefile(old_cfg, target):
                # This likely is caused by the symlink being
                # created early on an initial install.
                pass
            else:
                old_cfg.copy(target)
        else:
            self.cfg.copy(target)
            # TODO: Unneeded if copy old?
            self.run(["config", "set", "omero.web.server_list", self.args.web])

        log.debug('Configuring JVM memory')
        templates = self.dir / "etc" / "grid" / "templates.xml"
        for line in fileinput.input([templates], inplace=True):
            line = line.replace("Xmx512M", self.args.mem)
            line = line.replace("Xmx256M", self.args.mem)
            print line,

        self.configure_ports()

    def configure_ports(self):
        # Set registry, TCP and SSL ports
        self.run(["admin", "ports", "--skipcheck", "--registry",
                 self.args.registry, "--tcp",
                 self.args.tcp, "--ssl", self.args.ssl])

    def upgrade_db(self):
        if self.args.upgradedb:
            log.debug('Upgrading database')
            DbAdmin(self.dir, 'upgrade', self.args)

    def start(self):
        self.run("admin start")
        if self.web():
            log.info("Starting web")
            self.startweb()

    def run(self, command):
        """
        Runs a command as if from the command-line
        without the need for using popen or subprocess
        """
        if isinstance(command, str):
            command = command.split()
        else:
            command = list(command)
        self.external.omero_cli(command)

    def bin(self, command):
        """
        Runs the omero command-line client with an array of arguments using the
        old environment
        """
        if isinstance(command, str):
            command = command.split()
        self.external.omero_bin(command)

    def web(self):
        return "false" == self.args.skipweb.lower()


class UnixUpgrade(Upgrade):

    def stopweb(self):
        self.bin("web stop")

    def startweb(self):
        self.run("web start")

    def directories(self):
        if os.path.samefile(self.dir, self.args.sym):
            log.warn("Upgraded server was the same, not deleting")
            return

        target = os.readlink(self.args.sym)
        # normpath in case there's a trailing /
        targetzip = os.path.normpath(target) + '.zip'

        if "false" == self.args.skipdelete.lower():
            try:
                log.info("Deleting %s", target)
                shutil.rmtree(target)
            except OSError as e:
                log.error("Failed to delete %s: %s", target, e)

        if "false" == self.args.skipdeletezip.lower():
            try:
                log.info("Deleting %s", targetzip)
                os.unlink(targetzip)
            except OSError as e:
                log.error("Failed to delete %s: %s", targetzip, e)

        try:
            os.unlink(self.args.sym)
        except OSError as e:
            log.error("Failed to unlink %s: %s", self.args.sym, e)

        self.mklink(self.dir)

    def mklink(self, dir):
        try:
            os.symlink(dir, self.args.sym)
        except OSError as e:
            log.error("Failed to symlink %s to %s: %s", dir, self.args.sym, e)


class WindowsUpgrade(Upgrade):

    def stopweb(self):
        log.info("Removing web from IIS")
        self.bin("web iis --remove")
        self.iisreset()

    def startweb(self):
        log.info("Configuring web in IIS")
        self.run("web iis")
        self.iisreset()

    def directories(self):
        self.rmdir()  # TODO: skipdelete etc?
        log.warn(
            "Should probably move directory to OLD_OMERO and test handles")
        self.mklink(self.dir)

    def call(self, command):
        rc = subprocess.call(command, shell=True)
        if rc != 0:
            log.warn("'%s' returned with non-zero value: %s", command, rc)

    def rmdir(self):
        """
        """
        self.call("rmdir %s".split() % self.args.sym)

    def mklink(self, dir):
        """
        """
        self.call("mklink /d %s".split() % self.args.sym + ["%s" % dir])

    def iisreset(self):
        """
        Calls iisreset
        """
        self.call(["iisreset"])


class UpgradeCommand(Command):
    """
    Upgrade an existing OMERO installation.
    """

    NAME = "upgrade"

    def __init__(self, sub_parsers):
        super(UpgradeCommand, self).__init__(sub_parsers)

        # TODO: these are very internal values and should be refactored out
        # to a configure file.
        skipemail = "false"
        name = HOSTNAME
        if HOSTNAME == "gretzky":
            address = "gretzky.openmicroscopy.org.uk"
        elif HOSTNAME == "howe":
            address = "howe.openmicroscopy.org.uk"
        elif HOSTNAME == "ome-dev-svr":
            name = "win-2k8"
            address = "bp.openmicroscopy.org.uk"
        else:
            address = HOSTNAME
            # Don't send emails if we're not on a known host.
            skipemail = "true"

        self.parser.add_argument("-n", "--dry-run", action="store_true")
        self.parser.add_argument("server", nargs="?")

        self.parser = JenkinsParser(self.parser)
        self.parser = DbParser(self.parser)

        Add = EnvDefault.add
        Add(self.parser, "hostname", HOSTNAME)
        Add(self.parser, "name", name)
        Add(self.parser, "address", address)
        Add(self.parser, "skipemail", skipemail)

        # Ports
        Add(self.parser, "prefix", "")
        Add(self.parser, "registry", "%(prefix)s4061")
        Add(self.parser, "tcp", "%(prefix)s4063")
        Add(self.parser, "ssl", "%(prefix)s4064")

        # new_server.py
        cfg = os.path.join(os.path.expanduser("~"), "config.xml")
        Add(self.parser, "mem", "Xmx1024M")
        Add(self.parser, "sym", "OMERO-CURRENT")
        Add(self.parser, "cfg", cfg)

        web = """[["localhost", %(ssl)s, "%(name)s"]"""
        web += """, ["gretzky.openmicroscopy.org.uk", 4064, "gretzky"]"""
        web += """, ["howe.openmicroscopy.org.uk", 4064, "howe"]]"""
        Add(self.parser, "web", web)

        # send_email.py
        Add(self.parser, "subject", "OMERO - %(name)s was upgraded")
        Add(self.parser, "sender", "sysadmin@openmicroscopy.org")
        Add(self.parser, "recipients",
            "ome-nitpick@lists.openmicroscopy.org.uk",
            help="Comma-separated list of recipients")
        Add(self.parser, "server", "%(name)s (%(address)s)")
        Add(self.parser, "smtp_server", "smtp.dundee.ac.uk")
        Add(self.parser, "weburl", "http://%(address)s/omero/webclient/")

        Add(self.parser, "skipweb", "false")
        Add(self.parser, "skipdelete", "true")
        Add(self.parser, "skipdeletezip", "false")

        # Record the values of these environment variables in a file
        envvars = "ICE_HOME PATH DYLD_LIBRARY_PATH LD_LIBRARY_PATH PYTHONPATH"
        envvarsfile = os.path.join("%(sym)s", "omero.envvars")
        Add(self.parser, "savevars", envvars)
        Add(self.parser, "savevarsfile", envvarsfile)

        self.parser.add_argument("--upgradedb", action="store_true")

    def __call__(self, args):
        super(UpgradeCommand, self).__call__(args)
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
            if value and isinstance(value, (str, unicode)):
                replacement = value % dict(args._get_kwargs())
                log.debug("% 20s => %s" % (dest, replacement))
                setattr(args, dest, replacement)

        if args.dry_run:
            return

        artifacts = Artifacts(args)

        if not args.server:
            if args.skipunzip:
                raise Stop(0, 'Unzip disabled, exiting')

            dir = artifacts.download('server')
            # Exits if directory does not exist!
        else:
            dir = args.server

        if WINDOWS:
            WindowsUpgrade(dir, args)
        else:
            UnixUpgrade(dir, args)

        if "false" == args.skipemail.lower():
            Email(artifacts, args)
        else:
            log.info("Skipping email")
