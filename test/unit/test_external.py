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
import subprocess

from omego.external import External, RunException


class TestRunException(object):

    def setup_method(self, method):
        self.ex = RunException(
            'Message', 'exe', ['arg1', 'arg2'], 1, 'out', 'err')

    def test_str(self):
        s = 'Message\ncommand: exe arg1 arg2\nreturn code: 1'
        assert str(self.ex) == s

    def test_fullstr(self):
        s = ('Message\ncommand: exe arg1 arg2\nreturn code: 1\n'
             'stdout: out\nstderr: err')
        assert self.ex.fullstr() == s


class TestExternal(object):

    def setup_method(self, method):
        self.ext = External()
        self.mox = mox.Mox()
        self.envfilename = 'test.env'

    def teardown_method(self, method):
        self.mox.UnsetStubs()

    def create_dummy_server_dir(self, d):
        # d must be a pytest tmpdir object
        d.ensure('lib', 'python', 'omero', 'cli', dir=True)
        d.ensure('bin', dir=True)

        f = d.join(self.envfilename)
        f.write('TEST_ENVVAR1=abcde\nTEST_ENVVAR2=1=2=3=4=5\n')

    # def test_setup_omero_cli(self):
    # Not easily testable since it does a direct import

    def test_setup_previous_omero_env(self, tmpdir):
        self.create_dummy_server_dir(tmpdir)
        savevarsfile = str(tmpdir.join(self.envfilename))

        self.ext.setup_previous_omero_env(str(tmpdir), savevarsfile)
        env = self.ext.old_env
        assert env['PATH'].split(':', 1)[0] == os.path.join(str(tmpdir), 'bin')
        assert env['PYTHONPATH'].split(':', 1)[0] == os.path.join(
            str(tmpdir), 'lib', 'python')
        assert env['TEST_ENVVAR1'] == 'abcde'
        assert env['TEST_ENVVAR2'] == '1=2=3=4=5'

    def test_new_omero(self):
        class MockCli:
            def invoke(*args, **kwargs):
                assert args[1:] == (['arg1', 'arg2'], )
                assert kwargs == {'strict': True}

        self.ext.cli = MockCli()
        self.ext.new_omero(['arg1', 'arg2'])

    def test_old_omero(self):
        env = {'TEST': 'test'}
        self.ext.old_env = env
        self.mox.StubOutWithMock(self.ext, 'run')
        self.ext.run('omero', ['arg1', 'arg2'], env).AndReturn(0)
        self.mox.ReplayAll()

        self.ext.old_omero(['arg1', 'arg2'])
        self.mox.VerifyAll()

    def test_run(self):
        class MockProc:
            def __init__(self):
                self.returncode = 0

            def communicate(self):
                return 'ret1', 'ret2'

        env = {'TEST': 'test'}
        self.mox.StubOutWithMock(subprocess, 'Popen')
        subprocess.Popen(
            ['test', 'arg1', 'arg2'], env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).AndReturn(MockProc())
        subprocess.Popen(
            ['fail', 'arg1', 'arg2'], env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).AndRaise(RunException(
                'Message', 'fail', ['arg1', 'arg2'], 2, 'ret1', 'ret2'))
        self.mox.ReplayAll()

        self.ext.run('test', ['arg1', 'arg2'], env)
        with pytest.raises(RunException) as excinfo:
            self.ext.run('fail', ['arg1', 'arg2'], env)
        exc = excinfo.value
        assert exc.r == 2
        assert exc.message == 'Message'
        assert exc.stdout == 'ret1'
        assert exc.stderr == 'ret2'
        self.mox.VerifyAll()

    def test_get_environment(self, tmpdir):
        self.create_dummy_server_dir(tmpdir)
        savevarsfile = str(tmpdir.join(self.envfilename))
        env = self.ext.get_environment(savevarsfile)
        assert env['TEST_ENVVAR1'] == 'abcde'
        assert env['TEST_ENVVAR2'] == '1=2=3=4=5'

    def test_save_env_vars(self, tmpdir):
        savevarsfile = str(tmpdir.join(self.envfilename))

        self.mox.StubOutWithMock(os.environ, 'get')
        os.environ.get('TEST_ENVVAR1', '').AndReturn('abcde')
        self.mox.ReplayAll()

        self.ext.save_env_vars(savevarsfile, ['TEST_ENVVAR1'])
        with open(savevarsfile) as f:
            s = f.read()
        assert s == 'TEST_ENVVAR1=abcde\n'
        self.mox.VerifyAll()
