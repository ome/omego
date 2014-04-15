#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging

from urllib2 import build_opener, HTTPError
import re

from external import External, RunException
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


class ArtifactException(Exception):

    def __init__(self, msg, path):
        super(ArtifactException, self).__init__(msg)
        self.path = path

    def __str__(self):
        return '%s\npath: %s' % (
            super(ArtifactException, self).__str__(), self.path)


class ProgressBar(object):
    def __init__(self, ndots, total):
        self.ndots = ndots
        self.total = total
        self.n = 0
        self.marker = '*'
        self.pad = True

    def update(self, current):
        nextn = int(current * self.ndots / self.total)
        if nextn > self.n:
            self.n = nextn
            p = ''
            if self.pad:
                p = ' ' * (self.ndots - self.n) * len(self.marker)
            print '%s%s (%d/%d bytes)' % (
                self.marker * self.n, p, current, self.total)


def download(url, filename, print_progress=0):
    blocksize = 1024 * 1024
    downloaded = 0
    progress = None

    response = opener.open(url)
    try:
        total = int(response.headers['Content-Length'])

        if print_progress:
            progress = ProgressBar(print_progress, total)

        output = open(filename, 'wb')
        try:
            while downloaded < total:
                block = response.read(blocksize)
                output.write(block)
                downloaded += len(block)
                if progress:
                    progress.update(downloaded)
        finally:
            output.close()
    finally:
        response.close()


def rename_backup(name, suffix='.bak'):
    """
    Append a backup prefix to a file or directory, with an increasing numeric
    suffix (.N) if a file already exists
    """
    newname = '%s.bak' % name
    n = 0
    while os.path.exists(newname):
        n += 1
        newname = '%s.bak.%d' % (name, n)
    logging.info('Renaming %s to %s', name, newname)
    os.rename(name, newname)
    return newname


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

        log.info("Checking %s", componenturl)
        progress = 0
        if self.args.verbose:
            progress = 20
        ptype, localpath = self.get_as_local_path(
            componenturl, overwrite='keep', progress=progress)
        if ptype != 'file' or not localpath.endswith('.zip'):
            raise ArtifactException('Expected local zip file', localpath)

        if not self.args.skipunzip:
            try:
                unzipped = self.unzip(localpath)
                return unzipped
            except Exception as e:
                log.error('Unzip failed: %s', e)
                raise Stop(20, 'Unzip failed, try unzipping manually')

        return localpath

    def unzip(self, zipname, match_dir=True):
        """
        unzip an archive. Zips are assumed to unzip into a directory named
        after the zip (with the .zip extension removed). At present there is
        very limited error checking to verify this.

        zipname: The path to the zip file
        match_dir: If true an error will be raised if a directory named after
          the zip does not exist after unzipping
        """
        # TODO: Convert to pure python
        if not zipname.endswith('.zip'):
            raise ArtifactException('Expected zipname to end with .zip')
        command = self.args.unzip
        commandargs = []
        if self.args.unzipargs:
            commandargs.append(self.args.unzipargs)
        if self.args.unzipdir:
            commandargs.extend(["-d", self.args.unzipdir])
        commandargs.append(zipname)

        try:
            out, err = External.run(command, commandargs)
            log.debug(out)
            log.debug(err)
        except RunException as e:
            raise ArtifactException(str(e), zipname)

        unzipped = zipname[:-4]
        log.error('%s %s', zipname, unzipped)
        if self.args.unzipdir:
            unzipped = os.path.join(self.args.unzipdir, unzipped)
        if match_dir and not os.path.isdir(unzipped):
            raise ArtifactException(
                'Expected unzipped directory not found', unzipped)
        return unzipped

    def get_as_local_path(self, path, overwrite='error', progress=0):
        """
        Automatically handle local and remote URLs, files, directories and zips

        path: Either a local directory, file or remote URL. If a URL is given
          it will be fetched. If this is a zip it will be automatically
          expanded by default.
        overwrite: Whether to overwrite an existing file:
          'error': Raise an exception
          'backup: Renamed the old file and use the new one
          'keep': Keep the old file, don't overwrite or raise an exception
        progress: Number of progress dots, default 0 (don't print)
        TODO:
          httpuser, httppass: TODO: Credentials for HTTP authentication
        return: A tuple (type, localpath)
          type:
            'file': localpath is the path to a local file
            'directory': localpath is the path to a local directory
            'unzipped': localpath is the path to a local unzipped directory
        """
        m = re.match('([a-z]+)://', path)
        if m:
            protocol = m.group(1)
            if protocol not in ['http', 'https']:
                raise ArtifactException('Unsupported protocol' % path)

            # URL should use / as the pathsep
            localpath = path.split('/')[-1]
            if not localpath:
                raise ArtifactException(
                    'Remote path appears to be a directory', path)

            if os.path.exists(localpath):
                if overwrite == 'error':
                    raise ArtifactException('File already exists', localpath)
                elif overwrite == 'keep':
                    log.info('Keeping existing %s', localpath)
                elif overwrite == 'backup':
                    rename_backup(localpath)
                    download(path, localpath, progress)
                else:
                    raise Exception('Invalid overwrite flag: %s' % overwrite)
            else:
                download(path, localpath, progress)
        else:
            localpath = path
        log.debug("Local path: %s", localpath)

        if os.path.isdir(localpath):
            return 'directory', localpath
        if os.path.exists(localpath):
            return 'file', localpath

        # Somethings gone very wrong
        raise Exception('Local path does not exist: %s' % localpath)


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
