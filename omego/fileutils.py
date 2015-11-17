#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import os
import logging
import re
import urllib2
import tempfile
import zipfile

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


def open_url(url, httpuser=None, httppassword=None):
    """
    Open a URL using an opener that will simulate a browser user-agent
    url: The URL
    httpuser, httppassword: HTTP authentication credentials (either both or
      neither must be provided)
    """
    opener = urllib2.build_opener()
    if 'USER_AGENT' in os.environ:
        opener.addheaders = [('User-agent', os.environ.get('USER_AGENT'))]
        log.debug('Setting user-agent: %s', os.environ.get('USER_AGENT'))

    if httpuser and httppassword:
        mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, url, httpuser, httppassword)
        log.debug('Enabling HTTP authentication')
        opener.add_handler(urllib2.HTTPBasicAuthHandler(mgr))
        opener.add_handler(urllib2.HTTPDigestAuthHandler(mgr))
    elif httpuser or httppassword:
        raise FileException(
            'httpuser and httppassword must be used together', url)

    return opener.open(url)


def dereference_url(url):
    """
    Makes a HEAD request to find the final destination of a URL after
    following any redirects
    """
    req = urllib2.Request(url)
    req.get_method = lambda: 'HEAD'
    res = urllib2.urlopen(req)
    res.close()
    return res.url


def read(url, **kwargs):
    """
    Read the contents of a URL into memory, return
    """
    response = open_url(url, **kwargs)
    try:
        return response.read()
    finally:
        response.close()


def download(url, filename=None, print_progress=0, delete_fail=True,
             **kwargs):
    """
    Download a file, optionally printing a simple progress bar
    url: The URL to download
    filename: The filename to save to, default is to use the URL basename
    print_progress: The length of the progress bar, use 0 to disable
    delete_fail: If True delete the file if the download was not successful,
      default is to keep the temporary file
    return: The downloaded filename
    """
    blocksize = 1024 * 1024
    downloaded = 0
    progress = None

    log.info('Downloading %s', url)
    response = open_url(url, **kwargs)

    if not filename:
        filename = os.path.basename(url)

    output = None
    try:
        total = int(response.headers['Content-Length'])

        if print_progress:
            progress = ProgressBar(print_progress, total)

        with tempfile.NamedTemporaryFile(
                prefix=filename + '.', dir='.', delete=False) as output:
            while downloaded < total:
                block = response.read(blocksize)
                output.write(block)
                downloaded += len(block)
                if progress:
                    progress.update(downloaded)
        os.rename(output.name, filename)
        output = None
        return filename
    finally:
        response.close()
        if delete_fail and output:
            os.unlink(output.name)


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
    log.info('Renaming %s to %s', name, newname)
    os.rename(name, newname)
    return newname


def timestamp_filename(basename, ext=None):
    """
    Return a string of the form [basename-TIMESTAMP.ext]
    where TIMESTAMP is of the form YYYYMMDD-HHMMSS-MILSEC
    """
    dt = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    if ext:
        return '%s-%s.%s' % (basename, dt, ext)
    return '%s-%s' % (basename, dt)


def is_archive(filename):
    """
    Returns True if this is an expandable archive (currently only zips)
    """
    return filename.endswith('.zip')


def check_extracted_paths(namelist, subdir=None):
    """
    Check whether zip file paths are all relative, and optionally in a
    specified subdirectory, raises an exception if not

    namelist: A list of paths from the zip file
    subdir: If specified then check whether all paths in the zip file are
      under this subdirectory

    Python docs are unclear about the security of extract/extractall:
    https://docs.python.org/2/library/zipfile.html#zipfile.ZipFile.extractall
    https://docs.python.org/2/library/zipfile.html#zipfile.ZipFile.extract
    """
    def relpath(p):
        # relpath strips a trailing sep
        # Windows paths may also use unix sep
        q = os.path.relpath(p)
        if p.endswith(os.path.sep) or p.endswith('/'):
            q += os.path.sep
        return q

    parent = os.path.abspath('.')
    if subdir:
        if os.path.isabs(subdir):
            raise FileException('subdir must be a relative path', subdir)
        subdir = relpath(subdir + os.path.sep)

    for name in namelist:
        if os.path.commonprefix([parent, os.path.abspath(name)]) != parent:
            raise FileException('Insecure path in zipfile', name)

        if subdir and os.path.commonprefix(
                [subdir, relpath(name)]) != subdir:
            raise FileException(
                'Path in zipfile is not in required subdir', name)


def unzip(filename, match_dir=False, destdir=None):
    """
    Extract all files from a zip archive
    filename: The path to the zip file
    match_dir: If True all files in the zip must be contained in a subdirectory
      named after the archive file with extension removed
    destdir: Extract the zip into this directory, default current directory

    return: If match_dir is True then returns the subdirectory (including
      destdir), otherwise returns destdir or '.'
    """
    if not destdir:
        destdir = '.'

    z = zipfile.ZipFile(filename)
    unzipped = '.'

    if match_dir:
        if not filename.endswith('.zip'):
            raise FileException('Expected .zip file extension', filename)
        unzipped = os.path.basename(filename)[:-4]
        check_extracted_paths(z.namelist(), unzipped)
    else:
        check_extracted_paths(z.namelist())

    # File permissions, see
    # http://stackoverflow.com/a/6297838
    # http://stackoverflow.com/a/3015466
    for info in z.infolist():
        log.debug('Extracting %s to %s', info.filename, destdir)
        z.extract(info, destdir)
        perms = info.external_attr >> 16 & 4095
        if perms > 0:
            os.chmod(os.path.join(destdir, info.filename), perms)

    return os.path.join(destdir, unzipped)


def zip(filename, paths, strip_prefix=''):
    """
    Create a new zip archive containing files
    filename: The name of the zip file to be created
    paths: A list of files or directories
    strip_dir: Remove this prefix from all file-paths before adding to zip
    """
    if isinstance(paths, basestring):
        paths = [paths]

    filelist = set()
    for p in paths:
        if os.path.isfile(p):
            filelist.add(p)
        else:
            for root, dirs, files in os.walk(p):
                for f in files:
                    filelist.add(os.path.join(root, f))

    z = zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED)
    for f in sorted(filelist):
        arcname = f
        if arcname.startswith(strip_prefix):
            arcname = arcname[len(strip_prefix):]
        if arcname.startswith(os.path.sep):
            arcname = arcname[1:]
        log.debug('Adding %s to %s[%s]', f, filename, arcname)
        z.write(f, arcname)

    z.close()


def get_as_local_path(path, overwrite, progress=0,
                      httpuser=None, httppassword=None):
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
    httpuser, httppass: Credentials for HTTP authentication
    return: A tuple (type, localpath)
      type:
        'file': localpath is the path to a local file
        'directory': localpath is the path to a local directory
        'unzipped': localpath is the path to a local unzipped directory
    """
    m = re.match('([A-Za-z]+)://', path)
    if m:
        # url_open handles multiple protocols so don't bother validating
        log.debug('Detected URL protocol: %s', m.group(1))

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
                download(path, localpath, progress, httpuser=httpuser,
                         httppassword=httppassword)
            else:
                raise Exception('Invalid overwrite flag: %s' % overwrite)
        else:
            download(path, localpath, progress, httpuser=httpuser,
                     httppassword=httppassword)
    else:
        localpath = path
    log.debug("Local path: %s", localpath)

    if os.path.isdir(localpath):
        return 'directory', localpath
    if os.path.exists(localpath):
        return 'file', localpath

    # Somethings gone very wrong
    raise Exception('Local path does not exist: %s' % localpath)
