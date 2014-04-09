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
from omego.upgrade import UnixUpgrade


class TestUpgrade(object):

    class Args(object):
        def __init__(self, args):
            self.sym = 'sym'
            self.mem = '123'
            self.registry = '12'
            self.tcp = '34'
            self.ssl = '56'
            self.skipweb = 'false'
            self.skipdelete = 'false'
            self.skipdeletezip = 'false'
            for k, v in args.iteritems():
                setattr(self, k, v)

    class PartialMockUnixUpgrade(UnixUpgrade):

        def __init__(self, args, ext):
            self.args = args
            self.external = ext

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.UnsetStubs()

    @pytest.mark.parametrize('skipweb', [True, False])
    def test_stop(self, skipweb):
        ext = self.mox.CreateMock(External)
        ext.omero_bin(['admin', 'status', '--nodeonly'])
        ext.omero_bin(['admin', 'stop'])
        if not skipweb:
            ext.omero_bin(['web', 'stop'])
        self.mox.ReplayAll()

        args = self.Args({'skipweb': str(skipweb)})
        upgrade = self.PartialMockUnixUpgrade(args, ext)
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

        upgrade = self.PartialMockUnixUpgrade(args, ext)
        upgrade.configure_ports()
        self.mox.VerifyAll()

    @pytest.mark.parametrize('skipweb', [True, False])
    def test_start(self, skipweb):
        ext = self.mox.CreateMock(External)
        ext.omero_cli(['admin', 'start'])
        if not skipweb:
            ext.omero_cli(['web', 'start'])
        self.mox.ReplayAll()

        args = self.Args({'skipweb': str(skipweb)})
        upgrade = self.PartialMockUnixUpgrade(args, ext)
        upgrade.start()
        self.mox.VerifyAll()

    def test_run(self):
        ext = self.mox.CreateMock(External)
        ext.omero_cli(['a', 'b'])
        ext.omero_cli(['a', 'b'])
        self.mox.ReplayAll()

        upgrade = self.PartialMockUnixUpgrade({}, ext)
        upgrade.run('a b')
        upgrade.run(['a',  'b'])
        self.mox.VerifyAll()

    def test_bin(self):
        ext = self.mox.CreateMock(External)
        ext.omero_bin(['a', 'b'])
        ext.omero_bin(['a', 'b'])
        self.mox.ReplayAll()

        upgrade = self.PartialMockUnixUpgrade({}, ext)
        upgrade.bin('a b')
        upgrade.bin(['a', 'b'])
        self.mox.VerifyAll()

    @pytest.mark.parametrize('skipweb', [True, False])
    def test_web(self, skipweb):
        args = self.Args({'skipweb': str(skipweb)})
        upgrade = self.PartialMockUnixUpgrade(args, None)
        assert upgrade.web() != skipweb
        self.mox.VerifyAll()

    @pytest.mark.parametrize('skipdelete', [True, False])
    @pytest.mark.parametrize('skipdeletezip', [True, False])
    def test_directories(self, skipdelete, skipdeletezip):
        args = self.Args({'skipdelete': str(skipdelete),
                          'skipdeletezip': str(skipdeletezip)})
        upgrade = self.PartialMockUnixUpgrade(args, None)
        upgrade.dir = 'new'

        self.mox.StubOutWithMock(os.path, 'samefile')
        self.mox.StubOutWithMock(os, 'readlink')
        self.mox.StubOutWithMock(shutil, 'rmtree')
        self.mox.StubOutWithMock(os, 'unlink')
        self.mox.StubOutWithMock(upgrade, 'mklink')

        os.path.samefile('new', 'sym').AndReturn(False)
        os.readlink('sym').AndReturn('old/')
        if not skipdelete:
            shutil.rmtree('old/')
        if not skipdeletezip:
            os.unlink('old.zip')
        os.unlink('sym')
        upgrade.mklink('new')
        self.mox.ReplayAll()

        upgrade.directories()
        self.mox.VerifyAll()

    def test_mklink(self):
        args = self.Args({})
        upgrade = self.PartialMockUnixUpgrade(args, None)

        self.mox.StubOutWithMock(os, 'symlink')
        os.symlink('new', 'sym')
        self.mox.ReplayAll()

        upgrade.mklink('new')
        self.mox.VerifyAll()
