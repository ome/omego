#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import platform
import subprocess


def DEFINE(key, value):
    m = globals()
    m[key] = os.environ.get(key, value)
    print key, "=>", m[key]


###########################################################################
# DETECTION
###########################################################################
WINDOWS = platform.system() == "Windows"
p = subprocess.Popen(["hostname"], stdout=subprocess.PIPE)
h = p.communicate()[0].strip()
DEFINE("HOSTNAME", h)


###########################################################################
# CONFIGURATION
###########################################################################

# Most likely to be changed
DEFINE("NAME", HOSTNAME)
if HOSTNAME == "gretzky":
    DEFINE("ADDRESS", "gretzky.openmicroscopy.org.uk")
elif HOSTNAME == "howe":
    DEFINE("ADDRESS", "howe.openmicroscopy.org.uk")
elif HOSTNAME == "ome-dev-svr":
    DEFINE("NAME", "win-2k8")
    DEFINE("ADDRESS", "bp.openmicroscopy.org.uk")
else:
    DEFINE("ADDRESS", HOSTNAME)
    # Don't send emails if we're not on a known host.
    DEFINE("SKIPEMAIL", "true")
if "SKIPEMAIL" not in globals():
    DEFINE("SKIPEMAIL", "false")

if WINDOWS:
    DEFINE("UNZIP", "C:\\Program Files (x86)\\7-Zip\\7z.exe")
    DEFINE("UNZIPARGS", "x")
else:
    DEFINE("UNZIP", "unzip")
    DEFINE("UNZIPARGS", "")

# Ports
DEFINE("PREFIX", "")
DEFINE("REGISTRY" ,"%s4061" % PREFIX)
DEFINE("TCP" ,"%s4063" % PREFIX)
DEFINE("SSL" ,"%s4064" % PREFIX)

# new_server.py
DEFINE("MEM", "Xmx1024M")
DEFINE("SYM", "OMERO-CURRENT")
DEFINE("CFG", os.path.join(os.path.expanduser("~"), "config.xml"))
DEFINE("WEB", '[["localhost", %s, "%s"], ["gretzky.openmicroscopy.org.uk", 4064, "gretzky"], ["howe.openmicroscopy.org.uk", 4064, "howe"]]' % (SSL, NAME))

# send_email.py
DEFINE("SUBJECT", "OMERO - %s was upgraded" % NAME)
DEFINE("BRANCH", "OMERO-trunk")
DEFINE("BUILD", "http://hudson.openmicroscopy.org.uk/job/%s/lastSuccessfulBuild/" % BRANCH)
DEFINE("SENDER", "sysadmin@openmicroscopy.org")
DEFINE("RECIPIENTS", ["ome-nitpick@lists.openmicroscopy.org.uk"])
DEFINE("SERVER", "%s (%s)" % (NAME, ADDRESS))
DEFINE("SMTP_SERVER", "smtp.dundee.ac.uk")
DEFINE("WEBURL", "http://%s/omero/webclient/" % ADDRESS)

DEFINE("SKIPWEB", "false")
DEFINE("SKIPUNZIP", "false")


IS_JENKINS_JOB = all([key in os.environ for key in ["JOB_NAME",
    "BUILD_NUMBER", "BUILD_URL"]])
if IS_JENKINS_JOB:
    # Set BUILD_ID to DONT_KILL_ME to avoid server shutdown at job termination
    os.environ["BUILD_ID"] = "DONT_KILL_ME"
###########################################################################

import fileinput
import smtplib
import sys
import urllib
import re

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage

from zipfile import ZipFile

try:
    from xml.etree.ElementTree import XML, ElementTree, tostring
except ImportError:
    from elementtree.ElementTree import XML, ElementTree, tostring


class Artifacts(object):

    def __init__(self, build = BUILD):

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

    def __init__(self, artifacts, server = SERVER,\
            sender = SENDER, recipients = RECIPIENTS,\
            weburl = WEBURL, subject = SUBJECT,\
            smtp_server = SMTP_SERVER):

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

        print "Mail was sent to: %s" % ",".join(recipients)


class Upgrade(object):

    def __init__(self, dir, cfg = CFG, mem = MEM, sym = SYM, skipweb = SKIPWEB, registry = REGISTRY, tcp = TCP, ssl = SSL):

        print "%s: Upgrading %s (%s)..." % (self.__class__.__name__, dir, sym)

        self.mem = mem
        self.sym = sym
        self.skipweb = skipweb
        self.registry = registry
        self.tcp = tcp
        self.ssl = ssl

        _ = self.set_cli(self.sym)

        # Need lib/python set above
        import path
        self.cfg = path.path(cfg)
        self.dir = path.path(dir)

        self.stop(_)
        self.configure(_)
        self.directories(_)
        self.start(_)

    def stop(self, _):
        import omero
        try:
            print "Stopping server..."
            _("admin status --nodeonly")
            _("admin stop")
        except omero.cli.NonZeroReturnCode:
            pass

        if self.web():
            print "Stopping web..."
            self.stopweb(_)

    def configure(self, _):

        target = self.dir / "etc" / "grid" / "config.xml"
        if target.exists():
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
        _(["admin", "ports", "--registry", self.registry, "--tcp",
            self.tcp, "--ssl", self.ssl])

    def start(self, _):
        _("admin start")
        if self.web():
            print "Starting web ..."
            self.startweb(_)

    def set_cli(self, dir):

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
        self.cli.invoke(command, strict=True)

    def web(self):
        return "false" == self.skipweb.lower()


class UnixUpgrade(Upgrade):
    """
    def rmtree(self, d):
        def on_rmtree(self, func, name, exc):
            print "rmtree error: %s('%s') => %s" % (func.__name__, name, exc[1])
        d = path.path(d)
        d.rmtree(onerror = on_rmtree)
    """

    def stopweb(self, _):
        _("web stop")

    def startweb(self, _):
        _("web start")

    def directories(self, _):
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


if __name__ == "__main__":

    artifacts = Artifacts()

    if len(sys.argv) != 2:
        dir = artifacts.download('server')
        # Exits if directory does not exist!
    else:
        dir = sys.argv[1]

    if platform.system() != "Windows":
        u = UnixUpgrade(dir)
    else:
        u = WindowsUpgrade(dir)

    if "false" == SKIPEMAIL.lower():
        e = Email(artifacts)
    else:
        print "Skipping email..."
