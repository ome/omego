#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging

from HTMLParser import HTMLParser
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
        if args.build or re.match('[A-Za-z]\w+-\w+', args.branch):
            self.artifacts = JenkinsArtifacts(args)
        elif re.match('[0-9]+|latest$', args.branch):
            self.artifacts = ReleaseArtifacts(args)
        else:
            log.error('Invalid release or job name: %s', args.branch)
            raise Stop(20, 'Invalid release or job name: %s', args.branch)

    def download(self, component):
        componenturl = self.artifacts.get(component)
        if not componenturl:
            raise Exception("No %s found" % component)

        filename = os.path.basename(componenturl)
        unzipped = filename.replace(".zip", "")

        if os.path.exists(unzipped):
            self.create_symlink(unzipped)
            return unzipped

        log.info("Checking %s", componenturl)
        if self.args.dry_run:
            return

        progress = 0
        if self.args.verbose:
            progress = 20
        ptype, localpath = fileutils.get_as_local_path(
            componenturl, self.args.overwrite, progress=progress,
            httpuser=self.args.httpuser, httppassword=self.args.httppassword)
        if ptype != 'file':
            raise ArtifactException('Expected local file', localpath)

        if not self.args.skipunzip:
            if localpath.endswith('.zip'):
                try:
                    log.info('Unzipping %s', localpath)
                    unzipped = fileutils.unzip(
                        localpath, match_dir=True, destdir=self.args.unzipdir)
                    self.create_symlink(unzipped)
                    return unzipped
                except Exception as e:
                    log.error('Unzip failed: %s', e)
                    print e
                    raise Stop(20, 'Unzip failed, try unzipping manually')
            else:
                log.warn('Not unzipping %s', localpath)

        return localpath

    def list(self):
        s = ('Artifacts available for download. '
             'Initial partial matching is supported for all except '
             'named-components). '
             'Alternatively a full filename can be specified to download '
             'any artifact, including those not listed.\n' +
             str(self.artifacts))
        print s

    def create_symlink(self, localpath):
        sym = self.args.sym
        filename = os.path.basename(localpath)
        if sym and sym == 'auto':
            m = re.match('([A-Z]+\.\w+)-', filename)
            if m:
                sym = m.group(1)
            else:
                log.error('Failed to get symlink name for %s' % localpath)

        if sym:
            log.debug('Creating symlink %s -> %s', sym, localpath)
            try:
                os.unlink(sym)
            except OSError as e:
                pass

            try:
                os.symlink(os.path.abspath(localpath), sym)
            except OSError as e:
                log.error("Failed to symlink %s to %s: %s", filename, sym, e)
                raise


class ArtifactsList(object):
    """
    Searches for an artifact matching {NAME} using the following rules:
    1. Exact match to full filename
    2. Explicitly named matches
    3. OMERO.{NAME}*.zip
    4. {NAME}*.zip
    5. {NAME}*.jar
    Partial initial matching can be used except for full filenames
    """

    def __init__(self):
        self.filenames = {}
        self.namedcomponents = {}
        self.omerozips = {}
        self.zips = {}
        self.jars = {}

    @staticmethod
    def namedpatterns():
        return (
            ('win', r'OMERO\.insight.*-win\.zip$'),
            ('mac', r'OMERO\.insight.*-mac_Java7\+\.zip$'),
            ('mac6', r'OMERO\.insight.*-mac_Java6\.zip$'),
            ('linux', r'OMERO\.insight.*-linux\.zip$'),
            ('matlab', r'OMERO\.matlab.*\.zip$'),
            ('server', r'OMERO\.server.*\.zip$'),
            ('python', r'OMERO\.py.*\.zip$'),
            ('source', r'openmicroscopy.*\.zip$'),
        )

    @staticmethod
    def generalpatterns():
        return (
            ('omerozips', r'OMERO\.(.*)\.zip$'),
            ('zips', r'(.*)\.zip$'),
            ('jars', r'(.*)\.jar$'),
        )

    @classmethod
    def get_artifacts_list(self):
        return [n[0] for n in self.namedpatterns()] + ['...']

    def get(self, component):
        def matchdict(d, component):
            matchnames = tuple(d.keys())
            matches = [m for m in matchnames if m.startswith(component)]
            if matches:
                shortest = min(matches, key=len)
                return d[shortest]

        try:
            return self.filenames[component]
        except KeyError:
            pass

        match = matchdict(self.namedcomponents, component)
        if match:
            return match

        for genname, pattern in self.generalpatterns():
            gengroup = getattr(self, genname)
            match = matchdict(gengroup, component)
            if match:
                return match

        raise ArtifactException('No match for component', component)

    def __str__(self):
        s = ''
        if self.namedcomponents:
            s += 'named-components:\n  ' + '\n  '.join(
                k for k in sorted(self.namedcomponents.keys()))
        for genname, v in self.generalpatterns():
            d = getattr(self, genname)
            if d:
                s += '\n%s:\n  ' % genname + '\n  '.join(sorted(d.keys()))
        return s

    def find_artifacts(self, artifacturls):

        for artifact in artifacturls:
            filename = artifact.split('/')[-1]
            self.filenames[filename] = artifact

            for name, pattern in self.namedpatterns():
                if re.match(pattern, filename):
                    self.namedcomponents[name] = artifact
                    log.debug('Set %s=%s', name, artifact)
                    break

            for genname, pattern in self.generalpatterns():
                m = re.match(pattern, filename)
                if m:
                    getattr(self, genname)[m.group(1)] = artifact
                    log.debug('Set %s %s=%s', genname, m.group(1), artifact)


class JenkinsArtifacts(ArtifactsList):

    def __init__(self, args):
        super(JenkinsArtifacts, self).__init__()

        self.args = args
        buildurl = args.build

        if not buildurl:
            buildurl = "%s/job/%s/lastSuccessfulBuild/" % (
                args.ci, args.branch)
        if not re.match('\w+://', buildurl):
            buildurl = 'http://%s' % buildurl

        log.debug("buildurl: %s", buildurl)

        root = self.read_xml(buildurl)
        if root.tag == "matrixBuild":
            runurls = self.get_latest_runs(root)
            buildurl = self.find_label_matches(runurls, args.ice)
            root = self.read_xml(buildurl)

        artifacts = root.findall("./artifact")
        base_url = buildurl + "artifact/"
        if len(artifacts) <= 0:
            raise AttributeError(
                "No artifacts, please check build on the CI server.")

        artifacturls = [
            base_url + a.find("relativePath").text for a in artifacts]
        self.find_artifacts(artifacturls)

    def read_xml(self, buildurl):
        url = None
        try:
            url = fileutils.open_url(buildurl + 'api/xml',
                                     httpuser=self.args.httpuser,
                                     httppassword=self.args.httppassword)
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

    def find_label_matches(self, urls, icever=None):
        # The Ice version is handled as a matrix label in the CI jobs
        required = set(self.args.labels.split(','))
        if '' in required:
            required.remove('')
        if icever:
            required.add('ICE=%s' % icever)
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


class HtmlHrefParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self.hrefs = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for k, v in attrs:
                if k == 'href':
                    self.hrefs.add(v)


class ReleaseArtifacts(ArtifactsList):
    """
    Fetch artifacts from the download pages created for each release
    """

    def __init__(self, args):
        super(ReleaseArtifacts, self).__init__()
        self.args = args

        if re.match('[0-9]+\.[0-9]+\.[0-9]+', args.branch):
            ver = args.branch
            dl_url = '%s/omero/%s/' % (args.downloadurl, ver)
        elif re.match('[0-9]+|latest$', args.branch):
            dl_url = self.follow_latest_redirect(args)

        dl_icever = self.read_downloads(dl_url + 'artifacts/')
        if not args.ice:
            ice_ver = sorted(dl_icever.keys())[-1]
        else:
            ice_ver = 'ice%s' % args.ice.replace('.', '')
            if ice_ver not in dl_icever.keys():
                raise AttributeError(
                    "No artifacts found for ice version: %s" % ice_ver)

        artifacturls = dl_icever[ice_ver]

        if len(artifacturls) <= 0:
            raise AttributeError(
                "No artifacts, please check the downloads page.")
        self.find_artifacts(artifacturls)

    def follow_latest_redirect(self, args):
        ver = ''
        if args.branch != 'latest':
            ver = args.branch

        try:
            latesturl = '%s/latest/omero%s' % (args.downloadurl, ver)
            finalurl = fileutils.dereference_url(latesturl)
            log.debug('Checked %s: %s', latesturl, finalurl)
        except HTTPError as e:
            log.error('Invalid URL %s: %s', latesturl, e)
            raise Stop(20, 'Invalid latest URL, is the version correct?')
        return finalurl

    @staticmethod
    def read_downloads(dlurl):
        url = None
        parser = HtmlHrefParser()
        try:
            url = fileutils.open_url(dlurl)
            log.debug('Fetching html from %s code:%d', url.url, url.code)
            if url.code != 200:
                log.error('Failed to get HTML from %s (code %d)',
                          url.url, url.code)
                raise Stop(
                    20, 'Downloads page failed, is the version correct?')
            parser.feed(url.read())
        except HTTPError as e:
            log.error('Failed to get HTML from %s (%s)', dlurl, e)
            raise Stop(20, 'Downloads page failed, is the version correct?')
        finally:
            if url:
                url.close()

        dl_icever = {}
        for href in parser.hrefs:
            try:
                icever = re.search('-(ice\d+).*zip$', href).group(1)
                if re.match('\w+://', href):
                    fullurl = href
                else:
                    fullurl = dlurl + href
                try:
                    dl_icever[icever].append(fullurl)
                except KeyError:
                    dl_icever[icever] = [fullurl]
                log.debug('Found artifact: %s', fullurl)
            except AttributeError:
                pass

        return dl_icever


class DownloadCommand(Command):
    """
    Download an OMERO artifact from either a downloads or a Continuous
    Integration server.
    """

    NAME = "download"

    def __init__(self, sub_parsers):
        super(DownloadCommand, self).__init__(sub_parsers)

        self.parser.add_argument("-n", "--dry-run", action="store_true")
        self.parser.add_argument("artifact", nargs='?', default='', help=(
            "The artifact to download e.g. {%s}. "
            "Omit this argument to list all zip and jar artifacts" %
            ','.join(ArtifactsList.get_artifacts_list())))

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
        if args.artifact:
            artifacts.download(args.artifact)
        else:
            artifacts.list()
