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
try:
    from mox3 import mox
except ImportError:
    import mox

import copy
import os
import shutil

from omego.external import External
from omego import fileutils
import omego.upgrade
from omego.upgrade import UnixInstall


class TestUpgrade(object):

    class Args(object):
        def __init__(self, args):
            self.sym = 'sym'
            self.no_start = False
            self.no_web = False
            self.delete_old = False
            self.keep_old_zip = False
            self.verbose = False
            for k, v in args.items():
                setattr(self, k, v)

        def __eq__(self, o):
            return self.__dict__ == o.__dict__

    class PartialMockUnixInstall(UnixInstall):

        def __init__(self, args, ext):
            self.args = args
            self.external = ext

    class MockArtifacts(object):

        def download(self, component):
            assert component == 'server'
            return 'server-dir'

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.UnsetStubs()

    @pytest.mark.parametrize('cmd,expected', [
        ('install', True),
        ('upgrade', False),
    ])
    def test_handle_args_deprecated(self, cmd, expected):
        args = self.Args({
            'initdb': False,
            'upgradedb': False,
            'managedb': False,
            'upgrade': False,
        })
        upgrade = self.PartialMockUnixInstall(args, None)
        args, newinstall = upgrade._handle_args(cmd, args)
        assert newinstall is expected

    @pytest.mark.parametrize('server', [None, 'local', 'remote'])
    def test_get_server_dir(self, server):
        ext = self.mox.CreateMock(External)
        self.mox.StubOutWithMock(omego.upgrade, 'Artifacts')
        self.mox.StubOutWithMock(fileutils, 'get_as_local_path')
        self.mox.StubOutWithMock(fileutils, 'unzip')

        args = self.Args({'server': None, 'skipunzip': False,
                          'overwrite': 'error', 'unzipdir': None,
                          'httpuser': 'user', 'httppassword': 'password'})
        if server == 'local':
            args.server = 'local-server-dir'
            fileutils.get_as_local_path(
                args.server, args.overwrite, progress=0,
                httpuser=args.httpuser, httppassword=args.httppassword
                ).AndReturn(('directory', 'local-server-dir'))
            expected = 'local-server-dir'
        elif server == 'remote':
            args.server = 'http://example.org/remote/server.zip'
            fileutils.get_as_local_path(
                args.server, args.overwrite, progress=0,
                httpuser=args.httpuser, httppassword=args.httppassword
                ).AndReturn(('file', 'server.zip'))
            fileutils.unzip(
                'server.zip', match_dir=True, destdir=args.unzipdir
                ).AndReturn('server')
            expected = 'server'
        else:
            artifact_args = copy.copy(args)
            artifact_args.sym = ''
            omego.upgrade.Artifacts(artifact_args).AndReturn(
                self.MockArtifacts())
            expected = 'server-dir'

        self.mox.ReplayAll()

        upgrade = self.PartialMockUnixInstall(args, ext)
        s = upgrade.get_server_dir()
        assert s == expected

        self.mox.VerifyAll()

    @pytest.mark.parametrize('noweb', [True, False])
    def test_stop(self, noweb):
        ext = self.mox.CreateMock(External)
        ext.omero_bin(['admin', 'status', '--nodeonly'])
        ext.omero_bin(['admin', 'stop'])
        if not noweb:
            ext.omero_bin(['web', 'stop'])
        self.mox.ReplayAll()

        args = self.Args({'no_web': noweb})
        upgrade = self.PartialMockUnixInstall(args, ext)
        print ('*** %s' % upgrade.args.__dict__)
        upgrade.stop()
        self.mox.VerifyAll()

    @pytest.mark.skipif(True, reason='Untestable: dynamic module import')
    def test_configure(self):
        pass

    @pytest.mark.parametrize('archivelogs', [None, 'archivelogs.zip'])
    def test_archive_logs(self, archivelogs):
        self.mox.StubOutWithMock(fileutils, 'zip')
        if archivelogs:
            fileutils.zip(
                archivelogs, os.path.join('sym', 'var', 'log'),
                os.path.join('sym', 'var'))
        self.mox.ReplayAll()

        args = self.Args({'archivelogs': archivelogs})
        upgrade = self.PartialMockUnixInstall(args, None)
        upgrade.archive_logs()
        self.mox.VerifyAll()

    @pytest.mark.parametrize('nostart', [True, False])
    @pytest.mark.parametrize('noweb', [True, False])
    def test_start(self, nostart, noweb):
        ext = self.mox.CreateMock(External)
        if not nostart:
            ext.omero_cli(['admin', 'start'])
            if not noweb:
                ext.omero_cli(['web', 'start'])
        self.mox.ReplayAll()

        args = self.Args({'no_web': noweb, 'no_start': nostart})
        upgrade = self.PartialMockUnixInstall(args, ext)
        upgrade.start()
        self.mox.VerifyAll()

    def test_run(self):
        ext = self.mox.CreateMock(External)
        ext.omero_cli(['a', 'b'])
        ext.omero_cli(['a', 'b'])
        self.mox.ReplayAll()

        upgrade = self.PartialMockUnixInstall({}, ext)
        upgrade.run('a b')
        upgrade.run(['a',  'b'])
        self.mox.VerifyAll()

    def test_bin(self):
        ext = self.mox.CreateMock(External)
        ext.omero_bin(['a', 'b'])
        ext.omero_bin(['a', 'b'])
        self.mox.ReplayAll()

        upgrade = self.PartialMockUnixInstall({}, ext)
        upgrade.bin('a b')
        upgrade.bin(['a', 'b'])
        self.mox.VerifyAll()

    @pytest.mark.parametrize('deleteold', [True, False])
    @pytest.mark.parametrize('keepoldzip', [True, False])
    def test_directories(self, deleteold, keepoldzip):
        args = self.Args({'delete_old': deleteold,
                          'keep_old_zip': keepoldzip})
        upgrade = self.PartialMockUnixInstall(args, None)
        upgrade.dir = 'new'

        self.mox.StubOutWithMock(os.path, 'samefile')
        self.mox.StubOutWithMock(os, 'readlink')
        self.mox.StubOutWithMock(shutil, 'rmtree')
        self.mox.StubOutWithMock(os, 'unlink')
        self.mox.StubOutWithMock(upgrade, 'symlink')

        os.path.samefile('new', 'sym').AndReturn(False)
        os.readlink('sym').AndReturn('old/')
        if deleteold:
            shutil.rmtree('old')
        if not keepoldzip:
            os.unlink('old.zip')
        os.unlink('sym')
        upgrade.symlink('new', 'sym')
        self.mox.ReplayAll()

        upgrade.directories()
        self.mox.VerifyAll()

    def test_symlink(self):
        args = self.Args({})
        upgrade = self.PartialMockUnixInstall(args, None)

        self.mox.StubOutWithMock(os, 'symlink')
        os.symlink('new', 'sym')
        self.mox.ReplayAll()

        upgrade.symlink('new', 'sym')
        self.mox.VerifyAll()
