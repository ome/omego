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

import pytest
import mox

import os

from omego import fileutils
from omego.external import External


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
            return 'x' * r

        def close(self):
            pass

    @pytest.mark.parametrize('filename', [True, False])
    def test_download(self, tmpdir, filename):
        url = 'http://example.org/test/file.dat'
        filesize = 2 * 1024 * 1024 + 1
        self.mox.StubOutWithMock(fileutils.opener, 'open')
        fileutils.opener.open(url).AndReturn(self.MockResponse(filesize))
        self.mox.ReplayAll()

        with tmpdir.as_cwd():
            if filename:
                output = 'test.name'
                f = fileutils.download(url, output)
            else:
                output = 'file.dat'
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

    @pytest.mark.parametrize('matchdir', [True, False])
    @pytest.mark.parametrize('correctdir', [True, False])
    def test_unzip(self, matchdir, correctdir):
        self.mox.StubOutWithMock(External, 'run')
        self.mox.StubOutWithMock(os.path, 'isdir')

        External.run('/test/unzip', [
            '-unzipargs', '-d', 'unzip/dir', 'test.zip']).AndReturn(('', ''))
        if matchdir:
            os.path.isdir('unzip/dir/test').AndReturn(correctdir)

        self.mox.ReplayAll()

        args = {
            'unzip': '/test/unzip',
            'unzipargs': '-unzipargs',
            'unzipdir': 'unzip/dir'
        }

        if correctdir or (not correctdir and not matchdir):
            assert fileutils.unzip('test.zip', matchdir, **args
                ) == 'unzip/dir/test'
        else:
            with pytest.raises(fileutils.FileException):
                fileutils.unzip('test.zip', **args)
        self.mox.VerifyAll()

    @pytest.mark.parametrize('exists', [True, False])
    @pytest.mark.parametrize('remote', [True, False])
    @pytest.mark.parametrize('overwrite', ['error', 'backup', 'keep'])
    def test_get_as_local_path(self, exists, remote, overwrite):
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

        if remote:
            os.path.exists(expectedp).AndReturn(exists)

        if remote and exists and overwrite == 'backup':
            fileutils.rename_backup(expectedp)
            fileutils.download(p, expectedp, 0)

        if remote and not exists:
            fileutils.download(p, expectedp, 0)

        if not remote or (remote and not exists) or (
                remote and exists and overwrite != 'error'):
            os.path.isdir(expectedp).AndReturn(False)
            os.path.exists(expectedp).AndReturn(True)

        self.mox.ReplayAll()

        if remote and exists and overwrite == 'error':
            with pytest.raises(fileutils.FileException):
                fileutils.get_as_local_path(p, overwrite=overwrite)
        else:
            ptype, lpath = fileutils.get_as_local_path(p, overwrite=overwrite)
            assert ptype == 'file'
            assert lpath == expectedp

        self.mox.VerifyAll()
