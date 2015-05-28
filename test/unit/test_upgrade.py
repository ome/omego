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
import shutil

from omego.external import External
from omego import fileutils
import omego.upgrade
from omego.upgrade import UnixInstall


class TestUpgrade(object):

    class Args(object):
        def __init__(self, args):
            self.sym = 'sym'
            self.registry = '12'
            self.tcp = '34'
            self.ssl = '56'
            self.skipweb = 'false'
            self.skipdelete = 'false'
            self.skipdeletezip = 'false'
            self.verbose = False
            for k, v in args.iteritems():
                setattr(self, k, v)

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
            omego.upgrade.Artifacts(args).AndReturn(self.MockArtifacts())
            expected = 'server-dir'

        self.mox.ReplayAll()

        upgrade = self.PartialMockUnixInstall(args, ext)
        s = upgrade.get_server_dir()
        assert s == expected

        self.mox.VerifyAll()

    @pytest.mark.parametrize('skipweb', [True, False])
    def test_stop(self, skipweb):
        ext = self.mox.CreateMock(External)
        ext.omero_bin(['admin', 'status', '--nodeonly'])
        ext.omero_bin(['admin', 'stop'])
        if not skipweb:
            ext.omero_bin(['web', 'stop'])
        self.mox.ReplayAll()

        args = self.Args({'skipweb': str(skipweb)})
        upgrade = self.PartialMockUnixInstall(args, ext)
        print '*** %s' % upgrade.args.__dict__
        print upgrade.web()
        upgrade.stop()
        self.mox.VerifyAll()

    @pytest.mark.skipif(True, reason='Untestable: dynamic module import')
    def test_configure(self):
        pass

    def test_configure_ports(self):
        ext = self.mox.CreateMock(External)
        args = self.Args({})
        ext.omero_cli(
            ['admin', 'ports', '--skipcheck', '--registry', args.registry,
             '--tcp', args.tcp, '--ssl', args.ssl])
        self.mox.ReplayAll()

        upgrade = self.PartialMockUnixInstall(args, ext)
        upgrade.configure_ports()
        self.mox.VerifyAll()

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

    @pytest.mark.parametrize('skipweb', [True, False])
    def test_start(self, skipweb):
        ext = self.mox.CreateMock(External)
        ext.omero_cli(['admin', 'start'])
        if not skipweb:
            ext.omero_cli(['web', 'start'])
        self.mox.ReplayAll()

        args = self.Args({'skipweb': str(skipweb)})
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

    @pytest.mark.parametrize('skipweb', [True, False])
    def test_web(self, skipweb):
        args = self.Args({'skipweb': str(skipweb)})
        upgrade = self.PartialMockUnixInstall(args, None)
        assert upgrade.web() != skipweb
        self.mox.VerifyAll()

    @pytest.mark.parametrize('skipdelete', [True, False])
    @pytest.mark.parametrize('skipdeletezip', [True, False])
    def test_directories(self, skipdelete, skipdeletezip):
        args = self.Args({'skipdelete': str(skipdelete),
                          'skipdeletezip': str(skipdeletezip)})
        upgrade = self.PartialMockUnixInstall(args, None)
        upgrade.dir = 'new'

        self.mox.StubOutWithMock(os.path, 'samefile')
        self.mox.StubOutWithMock(os, 'readlink')
        self.mox.StubOutWithMock(shutil, 'rmtree')
        self.mox.StubOutWithMock(os, 'unlink')
        self.mox.StubOutWithMock(upgrade, 'symlink')

        os.path.samefile('new', 'sym').AndReturn(False)
        os.readlink('sym').AndReturn('old/')
        if not skipdelete:
            shutil.rmtree('old')
        if not skipdeletezip:
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
