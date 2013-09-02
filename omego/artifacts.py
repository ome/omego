#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import logging

import urllib
import re

from framework import Command, Stop
from env import JenkinsParser

try:
    from xml.etree.ElementTree import XML
except ImportError:
    from elementtree.ElementTree import XML

log = logging.getLogger("omego.artifacts")


class Artifacts(object):

    def __init__(self, args):

        self.args = args
        url = urllib.urlopen(args.build+"api/xml")
        log.debug('Fetching xml from %s code:%d', url.url, url.code)
        if url.code != 200:
            log.error('Failed to get Hudson XML from %s (code %d)',
                      url.url, url.code)
            raise Stop(20, 'Job lookup failed, is the job name correct?')
        hudson_xml = url.read()
        url.close()

        root = XML(hudson_xml)

        artifacts = root.findall("./artifact")
        base_url = args.build+"artifact/"
        if len(artifacts) <= 0:
            raise AttributeError("No artifacts, please check build on Hudson.")

        patterns = self.get_artifacts_list()
        for artifact in artifacts:
            filename = artifact.find("fileName").text

            for key, value in patterns.iteritems():
                if re.compile(value).match(filename):
                    rel_path = base_url + artifact.find("relativePath").text
                    setattr(self, key, rel_path)
                    pass

    @classmethod
    def get_artifacts_list(self):
        return {'server': r'OMERO\.server.*\.zip',
                'source': r'OMERO\.source.*\.zip',
                'win': r'OMERO\.clients.*\.win\.zip',
                'linux': r'OMERO\.clients.*\.linux\.zip',
                'mac': r'OMERO\.clients.*\.mac\.zip',
                'matlab': r'OMERO\.matlab.*\.zip',
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
            log.info("Downloading %s", componenturl)
            urllib.urlretrieve(componenturl, filename)

        if "false" == self.args.skipunzip.lower():
            if self.args.unzipargs:
                command = [self.args.unzip, self.args.unzipargs, filename]
            else:
                command = [self.args.unzip, filename]
            p = subprocess.Popen(command)
            rc = p.wait()
            if rc != 0:
                log.error('Unzip failed')
                raise Stop(rc, 'Unzip failed, unzip manually and run again')
            else:
                return unzipped
        else:
            return filename


class DownloadCommand(Command):
    """
    Download an OMERO artifact from a CI server.
    """

    NAME = "download"

    def __init__(self, sub_parsers):
        super(DownloadCommand, self).__init__(sub_parsers)

        self.parser.add_argument("-n", "--dry-run", action="store_true")
        self.parser.add_argument(
            "artifact",
            choices=Artifacts.get_artifacts_list().keys(),
            help="The artifact to download from the CI server")

        self.parser = JenkinsParser(self.parser)

    def __call__(self, args):
        super(DownloadCommand, self).__call__(args)
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
        artifacts.download(args.artifact)
