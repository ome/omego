#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import logging

import fileinput
import smtplib
import sys
import urllib
import re

from framework import Command
from env import EnvDefault
from env import WINDOWS
from env import HOSTNAME

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage

from zipfile import ZipFile

try:
    from xml.etree.ElementTree import XML, ElementTree, tostring
except ImportError:
    from elementtree.ElementTree import XML, ElementTree, tostring


log = logging.getLogger("omego.upgrade")


class Artifacts(object):

    def __init__(self, build):

        url = urllib.urlopen(build+"api/xml")
        hudson_xml = url.read()
        url.close()

        root = XML(hudson_xml)

        artifacts = root.findall("./artifact")
        base_url = build+"artifact/"
        if len(artifacts) <= 0:
            raise AttributeError("No artifacts, please check build on Hudson.")

        patterns = self.get_artifacts_list()
        for artifact in artifacts:
            filename = artifact.find("fileName").text

            for key, value in patterns.iteritems():
                if re.compile(value).match(filename):
                    setattr(self, key, base_url + artifact.find("relativePath").text)
                    pass

    def get_artifacts_list(self):
      return {
        'server':r'OMERO\.server.*\.zip',
        'source':r'OMERO\.source.*\.zip',
        'win':r'OMERO\.clients.*\.win\.zip',
        'linux':r'OMERO\.clients.*\.linux\.zip',
        'mac':r'OMERO\.clients.*\.mac\.zip',
        }

    def download(self, component):

        if not hasattr(self, component) or getattr(self, component) is None:
            raise Exception("No %s found" % component)

        componenturl = getattr(self, component)
        filename = os.path.basename(componenturl)
        unzipped = filename.replace(".zip", "")

        if os.path.exists(unzipped):
            return unzipped

        if not os.path.exists(filename):
            print "Downloading %s..." % componenturl
            urllib.urlretrieve(componenturl, filename)

        if "false" == SKIPUNZIP.lower():
            if UNZIPARGS:
                command = [UNZIP, UNZIPARGS, filename]
            else:
                command = [UNZIP, filename]
            p = subprocess.Popen(command)
            rc = p.wait()
            if rc != 0:
                print "Couldn't unzip!"
            else:
                return unzipped

        print "Unzip and run again"
        sys.exit(0)


class Email(object):

    def __init__(self, artifacts, server,\
            sender, recipients,\
            weburl, subject,\
            smtp_server):

        TO = ",".join(recipients)
        FROM = sender
        text = "The OMERO.server on %s has been upgraded. \n" \
                    "=========================\n" \
                    "THIS SERVER REQUIRES VPN!\n" \
                    "=========================\n" \
                    "Please download suitable clients from: \n " \
                    "\n - Windows: \n %s\n " \
                    "\n - MAC: \n %s\n " \
                    "\n - Linux: \n %s\n " \
                    "\n - Webclient available on %s. \n \n " %\
                    (server, artifacts.win, artifacts.mac, artifacts.linux,
                    weburl)
        BODY = "\r\n".join((
                "From: %s" % FROM,
                "To: %s" % TO,
                "Subject: %s" % subject,
                "",
                text))
        server = smtplib.SMTP(smtp_server)
        server.sendmail(FROM, recipients, BODY)
        server.quit()

        print "Mail was sent to: %s" % recipients


class Upgrade(object):

    def __init__(self, dir, cfg, mem, sym, skipweb,
                 registry, tcp, ssl,
                 savevars, savevarsfile):

        print "%s: Upgrading %s (%s)..." % (self.__class__.__name__, dir, sym)

        self.mem = mem
        self.sym = sym
        self.skipweb = skipweb
        self.registry = registry
        self.tcp = tcp
        self.ssl = ssl

        # setup_script_environment() may cause the creation of a default
        # config.xml, so we must check for it here
        noconfigure = self.has_config(dir)

        cli = self.setup_script_environment(dir)
        bin = self.setup_previous_omero_env(sym, savevarsfile)

        # Need lib/python set above
        import path
        self.cfg = path.path(cfg)
        self.dir = path.path(dir)

        self.stop(bin)

        self.configure(cli, noconfigure)
        self.directories(cli)

        self.save_env_vars(savevarsfile, savevars.split())
        self.start(cli)

    def stop(self, _):
        try:
            print "Stopping server..."
            _("admin status --nodeonly")
            _("admin stop")
        except Exception as e:
            print e

        if self.web():
            print "Stopping web..."
            self.stopweb(_)

    def has_config(self, dir):
        config = os.path.join(dir, "etc", "grid", "config.xml")
        return os.path.exists(config)

    def configure(self, _, noconfigure):

        target = self.dir / "etc" / "grid" / "config.xml"
        if noconfigure:
            print "Target %s already exists. Skipping..." % target
            self.configure_ports(_)
            return # Early exit!

        if not self.cfg.exists():
            print "%s not found. Copying old files" % self.cfg
            from path import path
            old_grid = path(self.sym) / "etc" / "grid"
            old_cfg = old_grid / "config.xml"
            old_cfg.copy(target)
        else:
            self.cfg.copy(target)
            _(["config", "set", "omero.web.server_list", WEB]) # TODO: Unneeded if copy old?

        for line in fileinput.input([self.dir / "etc" / "grid" / "templates.xml"], inplace=True):
            print line.replace("Xmx512M", self.mem).replace("Xmx256M", self.mem),

        self.configure_ports(_)

    def configure_ports(self, _):
        # Set registry, TCP and SSL ports
        _(["admin", "ports", "--skipcheck", "--registry", self.registry, "--tcp",
            self.tcp, "--ssl", self.ssl])

    def start(self, _):
        _("admin start")
        if self.web():
            print "Starting web ..."
            self.startweb(_)

    def setup_script_environment(self, dir):
        dir = os.path.abspath(dir)
        lib = os.path.join(dir, "lib", "python")
        if not os.path.exists(lib):
            raise Exception("%s does not exist!" % lib)
        sys.path.insert(0, lib)

        import omero
        import omero.cli

        print "Using %s..." % omero.cli.__file__

        self.cli = omero.cli.CLI()
        self.cli.loadplugins()
        return self._

    def setup_previous_omero_env(self, dir, savevarsfile):
        env = self.get_environment(savevarsfile)

        def addpath(varname, p):
            if not os.path.exists(p):
                raise Exception("%s does not exist!" % p)
            current = env.get(varname)
            if current:
                env[varname] = p + os.pathsep + current
            else:
                env[varname] = p

        dir = os.path.abspath(dir)
        lib = os.path.join(dir, "lib", "python")
        addpath("PYTHONPATH", lib)
        bin = os.path.join(dir, "bin")
        addpath("PATH", bin)
        self.old_env = env
        return self.bin

    def _(self, command):
        """
        Runs a command as if from the command-line
        without the need for using popen or subprocess
        """
        if isinstance(command, str):
            command = command.split()
        else:
            for idx, val in enumerate(command):
                command[idx] = val
        print "Invoking CLI [current environment]: %s" % " ".join(command)
        self.cli.invoke(command, strict=True)

    def bin(self, command):
        """
        Runs the omero command-line client with an array of arguments using the
        old environment
        """
        if isinstance(command, str):
            command = command.split()
        command.insert(0, 'omero')
        print "Running [old environment]: %s" % " ".join(command)
        r = subprocess.call(command, env=self.old_env)
        if r != 0:
            raise Exception("Non-zero return code: %d" % r)

    def web(self):
        return "false" == self.skipweb.lower()


    def get_environment(self, filename=None):
        env = os.environ.copy()
        if not filename:
            print "Using original environment"
            return env

        try:
            f = open(filename, "r")
            print "Loading old environment:"
            for line in f:
                key, value = line.strip().split("=", 1)
                env[key] = value
                print "  %s=%s" % (key, value)
        except Exception as e:
            print "WARNING: Failed to load environment variables from %s: %s" \
                % (filename, e)

        try:
            f.close()
        except:
            pass
        return env

    def save_env_vars(self, filename, varnames):
        try:
            f = open(filename, "w")
            print "Saving environment:"
            for var in varnames:
                value = os.environ.get(var, "")
                f.write("%s=%s\n" % (var, value))
                print "  %s=%s" % (var, value)
        except Exception as e:
            print "Failed to save environment variables to %s: %s" % (
                filename, e)

        try:
            f.close()
        except:
            pass



class UnixUpgrade(Upgrade):

    def stopweb(self, _):
        _("web stop")

    def startweb(self, _):
        _("web start")

    def directories(self, _):
        if os.path.samefile(self.dir, self.sym):
            print "Upgraded server was the same, not deleting"
            return

        target = os.readlink(self.sym)
        # normpath in case there's a trailing /
        targetzip = os.path.normpath(target) + '.zip'

        for delpath, flag in ((target, SKIPDELETE), (targetzip, SKIPDELETEZIP)):
            if "false" == flag.lower():
                try:
                    print "Deleting %s" % delpath
                    shutil.rmtree(delpath)
                except:
                    print "Failed to delete %s" % delpath

        try:
            os.unlink(self.sym)
        except:
            print "Failed to delete %s" % self.sym

        try:
            os.symlink(self.dir, self.sym)
        except:
            print "Failed to symlink %s to %s" % (self.dir, self.sym)


class WindowsUpgrade(Upgrade):

    def stopweb(self, _):
        print "Removing web from IIS ..."
        _("web iis --remove")
        self.iisreset()

    def startweb(self, _):
        print "Configuring web in IIS ..."
        _("web iis")
        self.iisreset()

    def directories(self, _):
        self.rmdir()
        print "Should probably move directory to OLD_OMERO and test handles"
        self.mklink(self.dir)

    def call(self, command):
        rc = subprocess.call(command, shell=True)
        if rc != 0:
            print "*"*80
            print "Warning: '%s' returned with non-zero value: %s" % (command, rc)
            print "*"*80

    def rmdir(self):
        """
        """
        self.call("rmdir %s".split() % self.sym)

    def mklink(self, dir):
        """
        """
        self.call("mklink /d %s".split() % self.sym + ["%s" % dir])

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

        ## TODO: these are very internal values and should be refactored out
        ## to a configure file.
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

        self.parser.add_argument("server", nargs="?")

        EnvDefault.add(self.parser, "hostname", HOSTNAME)
        EnvDefault.add(self.parser, "name", name)
        EnvDefault.add(self.parser, "address", address)
        EnvDefault.add(self.parser, "skipemail", skipemail)

        # UNZIP TOOLS
        if WINDOWS:
            unzip = "C:\\Program Files (x86)\\7-Zip\\7z.exe"
            unzipargs = "x"
        else:
            unzip = "unzip"
            unzipargs = ""

        EnvDefault.add(self.parser, "unzip", unzip)
        EnvDefault.add(self.parser, "unzipargs", unzipargs)

        # Ports
        EnvDefault.add(self.parser, "prefix", "")
        EnvDefault.add(self.parser, "registry", "%(prefix)s4061")
        EnvDefault.add(self.parser, "tcp", "%(prefix)s4063")
        EnvDefault.add(self.parser, "ssl", "%(prefix)s4064")

        # new_server.py
        cfg = os.path.join(os.path.expanduser("~"), "config.xml")
        EnvDefault.add(self.parser, "mem", "Xmx1024M")
        EnvDefault.add(self.parser, "sym", "OMERO-CURRENT")
        EnvDefault.add(self.parser, "cfg", cfg)

        web = """[["localhost", %(ssl)s, "%(name)s"], ["gretzky.openmicroscopy.org.uk", 4064, "gretzky"], ["howe.openmicroscopy.org.uk", 4064, "howe"]]"""
        EnvDefault.add(self.parser, "web", web)

        # send_email.py
        EnvDefault.add(self.parser, "subject", "OMERO - %(name)s was upgraded")
        EnvDefault.add(self.parser, "branch", "OMERO-trunk")
        EnvDefault.add(self.parser, "build", "http://hudson.openmicroscopy.org.uk/job/%(branch)s/lastSuccessfulBuild/")
        EnvDefault.add(self.parser, "sender", "sysadmin@openmicroscopy.org")
        EnvDefault.add(self.parser, "recipients", "ome-nitpick@lists.openmicroscopy.org.uk", help="Comma-separated list of recipients")
        EnvDefault.add(self.parser, "server", "%(name)s (%(address)s)")
        EnvDefault.add(self.parser, "smtp_server", "smtp.dundee.ac.uk")
        EnvDefault.add(self.parser, "weburl", "http://%(address)s/omero/webclient/")

        EnvDefault.add(self.parser, "skipweb", "false")
        EnvDefault.add(self.parser, "skipunzip", "false")
        EnvDefault.add(self.parser, "skipdelete", "true")
        EnvDefault.add(self.parser, "skipdeletezip", "false")

        # Record the values of these environment variables in a file
        EnvDefault.add(self.parser, "savevars", "ICE_HOME PATH DYLD_LIBRARY_PATH LD_LIBRARY_PATH PYTHONPATH")
        EnvDefault.add(self.parser, "savevarsfile", os.path.join("%(sym)s", "omero.envvars"))

    def __call__(self, args):
        super(UpgradeCommand, self).__call__(args)
        self.configure_logging(args)

        # Since EnvDefault.__action__ is only called if a user actively passes
        # a variable, there's no way to do the string replacing in the action
        # itself. Instead, we're post-processing them here, but this could be
        # improved.

        names = sorted(x.dest for x in self.parser._actions)
        for dest in names:
            if dest in ("help", "verbose", "quiet"): continue
            value = getattr(args, dest)
            if value and isinstance(value, (str, unicode)):
                replacement = value % dict(args._get_kwargs())
                log.debug("% 20s => %s" % (dest, replacement))
                setattr(args, dest, replacement)

        artifacts = Artifacts(build=args.build)

        if not args.server:
            dir = artifacts.download('server')
            # Exits if directory does not exist!
        else:
            dir = args.server

        if WINDOWS:
            U = WindowsUpgrade
        else:
            U = UnixUpgrade

        u = U(dir, cfg=args.cfg, mem=args.mem, sym=args.sym,
              skipweb=args.skipweb,
              registry=args.registry, tcp=args.tcp, ssl=args.ssl,
              savevars=args.savevars, savevarsfile=args.savevarsfile)

        if "false" == args.skipemail.lower():
            e = Email(artifacts, server = args.server,\
            sender = args.sender, recipients = args.recipients,\
            weburl = args.weburl, subject = args.subject,\
            smtp_server = args.smtp_server)
        else:
            print "Skipping email..."
