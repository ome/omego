#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import platform
import shutil
import subprocess
import sys


kvargs = {}
otherargs = []

for arg in sys.argv[1:]:
    try:
        k, v = arg.split('=', 1)
        kvargs[k] = v
    except:
        otherargs.append(arg)

def DEFINE(key, value):
    """
    Define a global variable using a value provided at the command line,
    as an environment variable or a default value
    """
    m = globals()
    if key in kvargs:
        m[key] = kvargs[key]
    else:
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
DEFINE("SKIPDELETE", "true")
DEFINE("SKIPDELETEZIP", "false")

# Record the values of these environment variables in a file
DEFINE("SAVEVARS", "ICE_HOME PATH DYLD_LIBRARY_PATH LD_LIBRARY_PATH PYTHONPATH")
DEFINE("SAVEVARSFILE", os.path.join(SYM, "omero.envvars"))


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

    def __init__(self, dir, cfg=CFG, mem=MEM, sym=SYM, skipweb=SKIPWEB,
                 registry=REGISTRY, tcp=TCP, ssl=SSL,
                 savevars=SAVEVARS, savevarsfile=SAVEVARSFILE):

        print "%s: Upgrading %s (%s)..." % (self.__class__.__name__, dir, sym)

        self.mem = mem
        self.sym = sym
        self.skipweb = skipweb
        self.registry = registry
        self.tcp = tcp
        self.ssl = ssl


        # Need lib/python set above
        import path
        self.cfg = path.path(cfg)
        self.dir = path.path(dir)
        self.env = None

        _ = self.set_omero(self.sym, self.get_environment(savevarsfile))
        self.stop(_)

        _ = self.set_omero(self.dir, self.get_environment())
        self.configure(_)
        self.directories(_)

        self.save_env_vars(savevarsfile, savevars.split())
        self.start(_)

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
        _(["admin", "ports", "--skipcheck", "--registry", self.registry, "--tcp",
            self.tcp, "--ssl", self.ssl])

    def start(self, _):
        _("admin start")
        if self.web():
            print "Starting web ..."
            self.startweb(_)

    def set_omero(self, dir, env):
        def addpath(varname, p):
            if not os.path.exists(p):
                raise Exception("%s does not exist!" % p)
            current = env.get(varname)
            if current:
                env[varname] = p + ':' + current
            else:
                env[varname] = p

        dir = os.path.abspath(dir)
        lib = os.path.join(dir, "lib", "python")
        addpath("PYTHONPATH", lib)
        bin = os.path.join(dir, "bin")
        addpath("PATH", bin)
        self.env = env
        return self._

    def _(self, command):
        """
        Runs the omero command-line client with an array of arguments
        """
        if isinstance(command, str):
            command = command.split()
        command.insert(0, 'omero')
        print "Running: %s" % command
        r = subprocess.call(command, env=self.env)
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

        if "false" == SKIPDELETE.lower():
            try:
                print "Deleting %s" % target
                shutil.rmtree(target)
            except:
                print "Failed to delete %s" % target

        if "false" == SKIPDELETEZIP.lower():
            try:
                targetzip = os.path.normpath(target) + '.zip'
                if os.path.exists(targetzip):
                    print "Deleting %s" % targetzip
                    os.unlink(targetzip)
            except:
                print "Failed to delete %s" % targetzip

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

    if len(otherargs) != 1:
        dir = artifacts.download('server')
        # Exits if directory does not exist!
    else:
        dir = otherargs[0]

    if platform.system() != "Windows":
        u = UnixUpgrade(dir)
    else:
        u = WindowsUpgrade(dir)

    if "false" == SKIPEMAIL.lower():
        e = Email(artifacts)
    else:
        print "Skipping email..."
