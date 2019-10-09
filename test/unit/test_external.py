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

from builtins import str
from builtins import object
import pytest
from mox3 import mox

import os
import subprocess
import tempfile

from omego import external


class TestRunException(object):

    def setup_method(self, method):
        self.ex = external.RunException(
            'Message', 'exe', ['arg1', 'arg2'], 1, 'out', 'err')

    def test_shortstr(self):
        s = 'Message\ncommand: exe arg1 arg2\nreturn code: 1'
        assert self.ex.shortstr() == s

    def test_fullstr(self):
        s = ('Message\ncommand: exe arg1 arg2\nreturn code: 1\n'
             'stdout: out\nstderr: err')
        assert self.ex.fullstr() == s


class TestExternal(object):

    def setup_method(self, method):
        self.ext = external.External()
        self.mox = mox.Mox()
        self.envfilename = 'test.env'

    def teardown_method(self, method):
        self.mox.UnsetStubs()

    def create_dummy_server_dir(self, d):
        # d must be a pytest tmpdir object
        d.ensure('lib', 'python', 'omero', 'cli', dir=True)
        d.ensure('etc', 'grid', dir=True)
        d.ensure('bin', dir=True)

        f = d.join(self.envfilename)
        f.write('TEST_ENVVAR1=abcde\nTEST_ENVVAR2=1=2=3=4=5\n')

    @pytest.mark.parametrize('configured', [True, False])
    def test_set_server_dir_and_has_config(self, tmpdir, configured):
        self.create_dummy_server_dir(tmpdir)
        if configured:
            tmpdir.ensure('etc', 'grid', 'config.xml')

        with pytest.raises(Exception) as excinfo:
            self.ext.has_config()
        assert str(excinfo.value) == 'No server directory set'

        with tmpdir.as_cwd():
            self.ext.set_server_dir('.')

        assert self.ext.dir == str(tmpdir)
        assert self.ext.has_config() == configured

        # Creating a config file should not change the original state
        tmpdir.ensure('etc', 'grid', 'config.xml')
        assert self.ext.has_config() == configured

    # def test_get_config(self):
    # Not easily testable since it requires the omero module

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

    def test_omero_cli(self):
        class MockCli(object):
            def invoke(*args, **kwargs):
                assert args[1:] == (['arg1', 'arg2'], )
                assert kwargs == {'strict': True}

        self.ext.cli = MockCli()
        self.ext.omero_cli(['arg1', 'arg2'])

    def test_omero_bin(self):
        env = {'TEST': 'test'}
        self.ext.old_env = env
        self.mox.StubOutWithMock(external, 'run')
        external.run('omero', ['arg1', 'arg2'], capturestd=True, env=env
                     ).AndReturn(0)
        self.mox.ReplayAll()

        self.ext.omero_bin(['arg1', 'arg2'])
        self.mox.VerifyAll()

    @pytest.mark.parametrize('retcode', [0, 1])
    @pytest.mark.parametrize('capturestd', [True, False])
    @pytest.mark.parametrize('windows', [True, False])
    def test_run(self, tmpdir, retcode, capturestd, windows):
        env = {'TEST': 'test'}
        self.mox.StubOutWithMock(subprocess, 'call')
        self.mox.StubOutWithMock(tempfile, 'TemporaryFile')
        self.mox.StubOutWithMock(external, 'WINDOWS')

        external.WINDOWS = windows

        if capturestd:
            outfile = open(str(tmpdir.join('std.out')), 'w+')
            outfile.write('out')
            errfile = open(str(tmpdir.join('std.err')), 'w+')
            errfile.write('err')

            tempfile.TemporaryFile().AndReturn(outfile)
            tempfile.TemporaryFile().AndReturn(errfile)
            subprocess.call(
                ['test', 'arg1', 'arg2'], env=env, shell=windows,
                stdout=outfile, stderr=errfile).AndReturn(retcode)
        else:
            subprocess.call(
                ['test', 'arg1', 'arg2'], env=env, shell=windows,
                stdout=None, stderr=None).AndReturn(retcode)
        self.mox.ReplayAll()

        if retcode == 0:
            stdout, stderr = external.run(
                'test', ['arg1', 'arg2'], capturestd, env)
        else:
            with pytest.raises(external.RunException) as excinfo:
                external.run('test', ['arg1', 'arg2'], capturestd, env)
            exc = excinfo.value
            assert exc.r == 1
            assert exc.args[0] == 'Non-zero return code'
            stdout = exc.stdout
            stderr = exc.stderr

        if capturestd:
            assert stdout == 'out'
            assert stderr == 'err'
            outfile.close()
            errfile.close()
        else:
            assert stdout is None
            assert stderr is None

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
