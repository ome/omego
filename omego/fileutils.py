#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import re
import urllib2

from external import External, RunException

log = logging.getLogger("omego.fileutils")


class FileException(Exception):

    def __init__(self, msg, path):
        super(FileException, self).__init__(msg)
        self.path = path

    def __str__(self):
        return '%s\npath: %s' % (
            super(FileException, self).__str__(), self.path)


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


def open_url(url, auth=None):
    """
    Open a URL using an opener that will simulate a browser user-agent
    url: The URL
    auth: Optional 2-tuple of authentication credentials (user, password)
    """
    opener = urllib2.build_opener()
    if 'USER_AGENT' in os.environ:
        opener.addheaders = [('User-agent', os.environ.get('USER_AGENT'))]
    if auth:
        mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, url, auth[0], auth[1])
        opener.add_handler(urllib2.HTTPBasicAuthHandler(mgr))
        opener.add_handler(urllib2.HTTPDigestAuthHandler(mgr))

    return opener.open(url)


def read(url, **kwargs):
    """
    Read the contents of a URL into memory, return
    """
    response = open_url(url, **kwargs)
    try:
        return response.read()
    finally:
        response.close()


def download(url, filename=None, print_progress=0, **kwargs):
    """
    Download a file, optionally printing a simple progress abar
    url: The URL to download
    filename: The filename to save to, default is to use the URL basename
    print_progress: The length of the progress bar, use 0 to disable
    return: The downloaded filename
    """
    blocksize = 1024 * 1024
    downloaded = 0
    progress = None

    response = open_url(url, **kwargs)

    if not filename:
        filename = os.path.basename(url)

    try:
        total = int(response.headers['Content-Length'])

        if print_progress:
            progress = ProgressBar(print_progress, total)

        with open(filename, 'wb') as output:
            while downloaded < total:
                block = response.read(blocksize)
                output.write(block)
                downloaded += len(block)
                if progress:
                    progress.update(downloaded)
        return filename
    finally:
        response.close()


def rename_backup(name, suffix='.bak'):
    """
    Append a backup prefix to a file or directory, with an increasing numeric
    suffix (.N) if a file already exists
    """
    newname = '%s%s' % (name, suffix)
    n = 0
    while os.path.exists(newname):
        n += 1
        newname = '%s%s.%d' % (name, suffix, n)
    logging.info('Renaming %s to %s', name, newname)
    os.rename(name, newname)
    return newname


def is_archive(filename):
    """
    Returns True if this is an expandable archive (currently only zips)
    """
    return filename.endswith('.zip')


def unzip(zipname, match_dir=True, **kwargs):
    """
    Unzip an archive. Zips are assumed to unzip into a directory named
    after the zip (with the .zip extension removed). At present there is
    very limited error checking to verify this.

    zipname: The path to the zip file
    match_dir: If true an error will be raised if a directory named after
    the zip does not exist after unzipping

    TODO: Rewrite in pure Python (otherwise we're dependent on the standard
    unzip being installed, which is unlikely on Windows)

    kwargs (will be ignored if None):
      unzip: The unzip executable to run. This is currently compulsory, at some
        point there will be built-in unzip functionality
      unzipargs: Additional arguments for unzip, will be split at whitespace
        TODO: Quoting isn't handled
      unzipdir: Pass a flag to unzip to indicate it should be expanded into a
        new directory
    """
    if not zipname.endswith('.zip'):
        raise FileException('Expected zipname to end with .zip')
    command = kwargs['unzip']
    commandargs = []
    if 'unzipargs' in kwargs:
        commandargs.extend(kwargs['unzipargs'].split())
    unzipdir = kwargs.get('unzipdir')
    if unzipdir:
        commandargs.extend(["-d", unzipdir])
    commandargs.append(zipname)

    try:
        out, err = External.run(command, commandargs)
        log.debug(out)
        log.debug(err)
    except RunException as e:
        raise FileException(str(e), zipname)

    unzipped = zipname[:-4]
    log.error('%s %s', zipname, unzipped)
    if unzipdir:
        unzipped = os.path.join(unzipdir, unzipped)
    if match_dir and not os.path.isdir(unzipped):
        raise FileException(
            'Expected unzipped directory not found', unzipped)
    return unzipped


def get_as_local_path(path, overwrite='error', progress=0):
    """
    Automatically handle local and remote URLs, files and directories

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
            raise FileException('Unsupported protocol' % path)

        # URL should use / as the pathsep
        localpath = path.split('/')[-1]
        if not localpath:
            raise FileException(
                'Remote path appears to be a directory', path)

        if os.path.exists(localpath):
            if overwrite == 'error':
                raise FileException('File already exists', localpath)
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
