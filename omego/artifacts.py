#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import logging

from urllib2 import build_opener, HTTPError
import re

from framework import Command, Stop
from env import JenkinsParser

try:
    from xml.etree.ElementTree import XML
except ImportError:
    from elementtree.ElementTree import XML

log = logging.getLogger("omego.artifacts")

# create an opener that will simulate a browser user-agent
opener = build_opener()
if 'USER_AGENT' in os.environ:
    opener.addheaders = [('User-agent', os.environ.get('USER_AGENT'))]


def download(url, filename):
    response = opener.open(url)
    try:
        output = open(filename, 'w')
        try:
            output.write(response.read())
        finally:
            output.close()
    finally:
        response.close()


class Artifacts(object):

    def __init__(self, args):

        self.args = args
        buildurl = args.build

        root = self.read_xml(buildurl)
        if root.tag == "matrixBuild":
            runs = root.findall("./run/url")
            buildurl = self.find_label_matches(r.text for r in runs)
            root = self.read_xml(buildurl)

        artifacts = root.findall("./artifact")
        base_url = buildurl + "artifact/"
        if len(artifacts) <= 0:
            raise AttributeError(
                "No artifacts, please check build on the CI server.")

        patterns = self.get_artifacts_list()
        for artifact in artifacts:
            filename = artifact.find("fileName").text

            for key, value in patterns.iteritems():
                if re.compile(value).match(filename):
                    rel_path = base_url + artifact.find("relativePath").text
                    setattr(self, key, rel_path)
                    pass

    def read_xml(self, buildurl):
        url = None
        try:
            url = opener.open(buildurl + 'api/xml')
            log.debug('Fetching xml from %s code:%d', url.url, url.code)
            if url.code != 200:
                log.error('Failed to get CI XML from %s (code %d)',
                          url.url, url.code)
                raise Stop(20, 'Job lookup failed, is the job name correct?')
            ci_xml = url.read()
        except HTTPError as e:
            log.error('Failed to get CI XML (%s)', e)
            raise Stop(20, 'Job lookup failed, is the job name correct?')
        finally:
            if url:
                url.close()

        root = XML(ci_xml)
        return root

    def find_label_matches(self, urls):
        required = set(self.args.labels.split(','))
        if '' in required:
            required.remove('')
        log.debug('Searching for matrix runs matching: %s', required)
        matches = []
        for url in urls:
            url_labels = self.label_list_parser(url)
            if len(required.intersection(url_labels)) == len(required):
                matches.append(url)

        if len(matches) != 1:
            log.error('Found %d matching matrix build runs: %s',
                      len(matches), matches)
            raise Stop(
                30, 'Expected one matching run, found %d' % len(matches))
        return matches[0]

    def label_list_parser(self, url):
        """
        Extracts comma separate tag=value pairs from a string
        Assumes all characters other than / and , are valid
        """
        labels = re.findall('([^/,]+=[^/,]+)', url)
        slabels = set(labels)
        if '' in slabels:
            slabels.remove('')
        return slabels

    @classmethod
    def get_artifacts_list(self):
        return {'server': r'OMERO\.server.*\.zip',
                'source': r'OMERO\.source.*\.zip',
                'win': r'OMERO\.clients.*\.win\.zip',
                'linux': r'OMERO\.clients.*\.linux\.zip',
                'mac': r'OMERO\.clients.*\.mac\.zip',
                'matlab': r'OMERO\.matlab.*\.zip',
                'cpp': r'OMERO\.cpp.*\.zip',
                }

    def download(self, component):

        if not hasattr(self, component) or getattr(self, component) is None:
            raise Exception("No %s found" % component)

        componenturl = getattr(self, component)
        filename = os.path.basename(componenturl)
        unzipped = filename.replace(".zip", "")

        if self.args.dry_run:
            return

        if os.path.exists(unzipped):
            return unzipped

        if not os.path.exists(filename):
            log.info("Downloading %s", componenturl)
            download(componenturl, filename)

        if not self.args.skipunzip:
            command = [self.args.unzip]
            if self.args.unzipargs:
                command.append(self.args.unzipargs)
            if self.args.unzipdir:
                command.extend(["-d", self.args.unzipdir])
            command.append(filename)
            log.debug("Calling %s", command)
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

        artifacts = Artifacts(args)
        artifacts.download(args.artifact)
