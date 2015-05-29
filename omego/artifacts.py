#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging

from urllib2 import HTTPError
import re

import fileutils
from yaclifw.framework import Command, Stop
from env import FileUtilsParser, JenkinsParser

try:
    from xml.etree.ElementTree import XML
except ImportError:
    from elementtree.ElementTree import XML

log = logging.getLogger("omego.artifacts")


class ArtifactException(Exception):

    def __init__(self, msg, path):
        super(ArtifactException, self).__init__(msg)
        self.path = path

    def __str__(self):
        return '%s\npath: %s' % (
            super(ArtifactException, self).__str__(), self.path)


class Artifacts(object):

    def __init__(self, args):

        self.args = args
        buildurl = args.build

        root = self.read_xml(buildurl)
        if root.tag == "matrixBuild":
            runurls = self.get_latest_runs(root)
            buildurl = self.find_label_matches(runurls)
            root = self.read_xml(buildurl)

        artifacts = root.findall("./artifact")
        base_url = buildurl + "artifact/"
        if len(artifacts) <= 0:
            raise AttributeError(
                "No artifacts, please check build on the CI server.")

        patterns = self.get_artifacts_list()
        for artifact in artifacts:
            filename = artifact.find("fileName").text

            for key, value in patterns:
                if re.compile(value).match(filename):
                    rel_path = base_url + artifact.find("relativePath").text
                    setattr(self, key, rel_path)
                    pass

    def read_xml(self, buildurl):
        url = None
        try:
            url = fileutils.open_url(buildurl + 'api/xml')
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

    def get_latest_runs(self, root):
        """
        Jenkins has a bug whereby it may return matrix sub-builds for older
        runs from different nodes in addition to the latest one, so we need
        to compare each run with the current build number
        """
        rurl = [u.text for u in root.findall('./url')]
        if len(rurl) != 1:
            log.error('Expected one root url, found %d: %s', len(rurl), rurl)
            raise Stop(20, 'Failed to parse CI XML')
        rurl = rurl[0]
        log.debug('Root url: %s', rurl)

        try:
            build = re.search('/(\d+)/?$', rurl).group(1)
        except:
            log.error('Failed to extract build number from url: %s', rurl)
            raise Stop(20, 'Failed to parse CI XML')

        runs = root.findall('./run')
        runurls = [
            r.find('url').text for r in runs if r.find('number').text == build]
        log.debug('Child runs: %s', runurls)
        if len(runurls) < 1:
            log.error('No runs found in build: %s', rurl)
            raise Stop(20, 'Failed to parse CI XML')

        return runurls

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
        return [
            ('win', r'OMERO\.insight.*-win\.zip'),
            ('mac', r'OMERO\.insight.*-mac_Java7\+\.zip'),
            ('mac6', r'OMERO\.insight.*-mac_Java6\.zip'),
            ('linux', r'OMERO\.insight.*-linux\.zip'),
            ('matlab', r'OMERO\.matlab.*\.zip'),
            ('server', r'OMERO\.server.*\.zip'),
            ('python', r'OMERO\.py.*\.zip'),
            ('source', r'openmicroscopy.*\.zip'),
            ('cpp', r'OMERO\.cpp.*\.zip'),
            ]

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

        log.info("Checking %s", componenturl)
        progress = 0
        if self.args.verbose:
            progress = 20
        ptype, localpath = fileutils.get_as_local_path(
            componenturl, self.args.overwrite, progress=progress,
            httpuser=self.args.httpuser, httppassword=self.args.httppassword)
        if ptype != 'file' or not localpath.endswith('.zip'):
            raise ArtifactException('Expected local zip file', localpath)

        if not self.args.skipunzip:
            try:
                log.info('Unzipping %s', localpath)
                unzipped = fileutils.unzip(
                    localpath, match_dir=True, destdir=self.args.unzipdir)
                return unzipped
            except Exception as e:
                log.error('Unzip failed: %s', e)
                print e
                raise Stop(20, 'Unzip failed, try unzipping manually')

        return localpath


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
            choices=[kv[0] for kv in Artifacts.get_artifacts_list()],
            help="The artifact to download from the CI server")

        self.parser = JenkinsParser(self.parser)
        self.parser = FileUtilsParser(self.parser)

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
            if value and isinstance(value, basestring):
                replacement = value % dict(args._get_kwargs())
                log.debug("% 20s => %s" % (dest, replacement))
                setattr(args, dest, replacement)

        artifacts = Artifacts(args)
        artifacts.download(args.artifact)
