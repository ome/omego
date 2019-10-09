#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2014 University of Dundee & Open Microscopy Environment
# All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from builtins import zip
from builtins import str
from builtins import range
from builtins import object
import pytest
from mox3 import mox

import os
import re
import zipfile

from omego import fileutils


class TestFileutils(object):

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.UnsetStubs()

    class MockResponse(object):

        def __init__(self, length):
            self.headers = {'Content-Length': str(length)}
            self.remaining = length

        def read(self, blocksize):
            assert self.remaining > 0
            r = min(blocksize, self.remaining)
            self.remaining -= r
            return b'x' * r

        def close(self):
            pass

    # TODO
    # def test_open_url

    # TODO
    # def test_read

    @pytest.mark.parametrize('filename', [True, False])
    @pytest.mark.parametrize('httpauth', [True, False])
    def test_download(self, tmpdir, filename, httpauth):
        url = 'http://example.org/test/file.dat'
        filesize = 2 * 1024 * 1024 + 1
        self.mox.StubOutWithMock(fileutils, 'open_url')
        if httpauth:
            fileutils.open_url(url, httpuser='user', httppassword='password'
                               ).AndReturn(self.MockResponse(filesize))
        else:
            fileutils.open_url(url).AndReturn(self.MockResponse(filesize))
        self.mox.ReplayAll()

        with tmpdir.as_cwd():
            if filename:
                output = 'test.name'
                if httpauth:
                    f = f = fileutils.download(url, output, httpuser='user',
                                               httppassword='password')
                else:
                    f = fileutils.download(url, output)
            else:
                output = 'file.dat'
                if httpauth:
                    f = f = fileutils.download(url, output, httpuser='user',
                                               httppassword='password')
                else:
                    f = fileutils.download(url)

            assert f == output
            assert os.path.exists(output)
            assert os.path.getsize(output) == filesize

        self.mox.VerifyAll()

    @pytest.mark.parametrize('exists', [True, False])
    @pytest.mark.parametrize('suffix', [True, False])
    def test_rename_backup(self, exists, suffix):
        self.mox.StubOutWithMock(os.path, 'exists')
        self.mox.StubOutWithMock(os, 'rename')

        input = 'test.dat'
        if suffix:
            backup = 'test.dat.testsuffix'
        else:
            backup = 'test.dat.bak'

        if exists == 0:
            os.path.exists(backup).AndReturn(False)
            output = backup
        if exists == 1:
            os.path.exists(backup).AndReturn(True)
            os.path.exists(backup + '.1').AndReturn(False)
            output = backup + '.1'
        if exists == 2:
            os.path.exists(backup).AndReturn(True)
            os.path.exists(backup + '.1').AndReturn(True)
            os.path.exists(backup + '.2').AndReturn(False)
            output = backup + '.2'

        os.rename(input, output)
        self.mox.ReplayAll()

        if suffix:
            b = fileutils.rename_backup(input, '.testsuffix')
        else:
            b = fileutils.rename_backup(input)
        assert b == output
        self.mox.VerifyAll()

    @pytest.mark.parametrize('ext', [True, False])
    def test_timestamp_filename(self, ext):
        if ext:
            s = fileutils.timestamp_filename('name', 'test')
            assert re.match(r'^name-\d{8}-\d{6}-\d{6}\.test$', s)
        else:
            s = fileutils.timestamp_filename('name')
            assert re.match(r'^name-\d{8}-\d{6}-\d{6}$', s)

    def test_check_extracted_paths(self):
        fileutils.check_extracted_paths(['a/', 'a/b'])
        fileutils.check_extracted_paths(['a/', 'a/b'], 'a')

        with pytest.raises(fileutils.FileException) as excinfo:
            fileutils.check_extracted_paths(['a', '/b'])
        assert excinfo.value.args[0] == 'Insecure path in zipfile'

        with pytest.raises(fileutils.FileException) as excinfo:
            fileutils.check_extracted_paths(['a', 'a/../..'])
        assert excinfo.value.args[0] == 'Insecure path in zipfile'

        with pytest.raises(fileutils.FileException) as excinfo:
            fileutils.check_extracted_paths(['a', '..'])
        assert excinfo.value.args[0] == 'Insecure path in zipfile'

        with pytest.raises(fileutils.FileException) as excinfo:
            fileutils.check_extracted_paths(['a', 'b/c'], 'a')
        assert excinfo.value.args[0] == (
            'Path in zipfile is not in required subdir')

    @pytest.mark.parametrize('destdir', ['.', 'testdir'])
    def test_unzip(self, destdir):
        class MockZipInfo(object):

            def __init__(self, name, perms):
                self.filename = name
                self.external_attr = perms << 16

        self.mox.StubOutClassWithMocks(zipfile, 'ZipFile')
        self.mox.StubOutWithMock(os, 'chmod')

        files = ['test/', 'test/a', 'test/b/', 'test/b/c']
        perms = [0o755, 0o644, 0o755, 0o550]
        infos = [MockZipInfo(f, p) for (f, p) in zip(files, perms)]

        mockzip = zipfile.ZipFile('path/to/test.zip')
        mockzip.namelist().AndReturn(files)
        mockzip.infolist().AndReturn(infos)
        for n in range(4):
            mockzip.extract(infos[n], destdir)
            os.chmod(os.path.join(destdir, files[n]), perms[n])

        self.mox.ReplayAll()

        if destdir == '.':
            unzipped = fileutils.unzip('path/to/test.zip', True)
        else:
            unzipped = fileutils.unzip('path/to/test.zip', True, destdir)
        assert unzipped == os.path.join(destdir, 'test')

        self.mox.VerifyAll()

    def test_zip(self):
        self.mox.StubOutClassWithMocks(zipfile, 'ZipFile')
        self.mox.StubOutWithMock(os, 'walk')
        self.mox.StubOutWithMock(os.path, 'isfile')

        # files = ['test', 'test/a', 'test/b', 'test/b/c']
        os.walk('test').AndReturn([
            ('test', ['b'], ['a']), ('test/b', [], ['c'])])
        os.path.isfile('test').AndReturn(False)

        mockzip = zipfile.ZipFile(
            'path/to/test.zip', 'w', zipfile.ZIP_DEFLATED)
        mockzip.write('test/a', 'a')
        mockzip.write('test/b/c', 'b/c')
        mockzip.close()

        self.mox.ReplayAll()
        fileutils.zip('path/to/test.zip', ['test'], 'test')
        self.mox.VerifyAll()

    @pytest.mark.parametrize('exists', [True, False])
    @pytest.mark.parametrize('remote', [True, False])
    @pytest.mark.parametrize('overwrite', ['error', 'backup', 'keep'])
    @pytest.mark.parametrize('httpauth', [True, False])
    def test_get_as_local_path(self, exists, remote, overwrite, httpauth):
        if remote:
            p = 'http://example.org/test.zip'
            expectedp = 'test.zip'
        else:
            p = '/example/test.zip'
            expectedp = p

        self.mox.StubOutWithMock(os.path, 'exists')
        self.mox.StubOutWithMock(os.path, 'isdir')
        self.mox.StubOutWithMock(fileutils, 'rename_backup')
        self.mox.StubOutWithMock(fileutils, 'download')

        if httpauth:
            kwargs = {'httpuser': 'user', 'httppassword': 'password'}
        else:
            kwargs = {'httpuser': None, 'httppassword': None}

        if remote:
            os.path.exists(expectedp).AndReturn(exists)

        if remote and exists and overwrite == 'backup':
            fileutils.rename_backup(expectedp)

        if (remote and exists and overwrite == 'backup') or (
                remote and not exists):
            fileutils.download(p, expectedp, 0, **kwargs)

        if not remote or (remote and not exists) or (
                remote and exists and overwrite != 'error'):
            os.path.isdir(expectedp).AndReturn(False)
            os.path.exists(expectedp).AndReturn(True)

        self.mox.ReplayAll()

        if remote and exists and overwrite == 'error':
            with pytest.raises(fileutils.FileException):
                fileutils.get_as_local_path(p, overwrite, **kwargs)
        else:
            ptype, lpath = fileutils.get_as_local_path(p, overwrite, **kwargs)
            assert ptype == 'file'
            assert lpath == expectedp

        self.mox.VerifyAll()
