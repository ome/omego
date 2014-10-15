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

from omego.external import External, RunException
from yaclifw.framework import Stop
import omego.db
import omego.fileutils
from omego.db import DbAdmin


class TestDb(object):

    class Args(object):
        def __init__(self, args):
            for k, v in args.iteritems():
                setattr(self, k, v)

    class PartialMockDb(DbAdmin):

        def __init__(self, args, ext):
            self.args = args
            self.external = ext
            self.dir = '.'

    def setup_method(self, method):
        self.mox = mox.Mox()

    def teardown_method(self, method):
        self.mox.UnsetStubs()

    @pytest.mark.parametrize('connected', [True, False])
    def test_check_connection(self, connected):
        db = self.PartialMockDb(None, None)
        self.mox.StubOutWithMock(db, 'psql')

        if connected:
            db.psql('-c', '\conninfo')
        else:
            db.psql('-c', '\conninfo').AndRaise(
                RunException('', '', [], 1, '', ''))
        self.mox.ReplayAll()

        if connected:
            db.check_connection()
        else:
            with pytest.raises(Stop) as excinfo:
                db.check_connection()
            assert str(excinfo.value) == 'Database connection check failed'

        self.mox.VerifyAll()

    @pytest.mark.parametrize('sqlfile', ['exists', 'missing', 'notprovided'])
    @pytest.mark.parametrize('dryrun', [True, False])
    def test_initialise(self, sqlfile, dryrun):
        ext = self.mox.CreateMock(External)
        if sqlfile != 'notprovided':
            omerosql = 'omero.sql'
        else:
            omerosql = None
        args = self.Args({'omerosql': omerosql, 'rootpass': 'rootpass',
                          'dry_run': dryrun})
        db = self.PartialMockDb(args, ext)
        self.mox.StubOutWithMock(db, 'psql')
        self.mox.StubOutWithMock(omego.fileutils, 'timestamp_filename')
        self.mox.StubOutWithMock(os.path, 'exists')

        if sqlfile == 'notprovided':
            omerosql = 'omero-00000000-000000-000000.sql'
            omego.fileutils.timestamp_filename('omero', 'sql').AndReturn(
                omerosql)
        else:
            os.path.exists(omerosql).AndReturn(sqlfile == 'exists')

        if sqlfile == 'notprovided' and not dryrun:
            ext.omero_cli([
                'db', 'script', '-f', omerosql, '', '', args.rootpass])

        if sqlfile != 'missing' and not dryrun:
            db.psql('-f', omerosql)

        self.mox.ReplayAll()

        if sqlfile == 'missing':
            with pytest.raises(Stop) as excinfo:
                db.initialise()
            assert str(excinfo.value) == 'SQL file not found'
        else:
            db.initialise()
        self.mox.VerifyAll()

    def test_sort_schema(self):
        ordered = ['OMERO3__0', 'OMERO3A__10', 'OMERO4__0', 'OMERO4.4__0',
                   'OMERO5.0__0', 'OMERO5.1DEV__0', 'OMERO5.1DEV__1',
                   'OMERO5.1DEV__2', 'OMERO5.1DEV__10',
                   'OMERO5.1__0']

        ps = [5, 3, 7, 9, 2, 6, 0, 1, 8, 4]
        permuted = [ordered[p] for p in ps]

        db = self.PartialMockDb(None, None)
        assert db.sort_schema(permuted) == ordered
        self.mox.VerifyAll()

    def test_sql_version_matrix(self):
        self.mox.StubOutWithMock(omego.db, 'glob')
        omego.db.glob(
            os.path.join('.', 'sql', 'psql', 'OMERO*', 'OMERO*.sql')
            ).AndReturn(['./sql/psql/OMERO5.0__0/OMERO4.4__0.sql',
                         './sql/psql/OMERO5.1__0/OMERO5.0__0.sql'])
        self.mox.ReplayAll()

        db = self.PartialMockDb(None, None)
        M, versions = db.sql_version_matrix()
        assert versions == ['OMERO4.4__0', 'OMERO5.0__0', 'OMERO5.1__0']
        assert M == [[None, './sql/psql/OMERO5.0__0/OMERO4.4__0.sql', None],
                     [None, None, './sql/psql/OMERO5.1__0/OMERO5.0__0.sql'],
                     [None, None, None]]
        self.mox.VerifyAll()

    @pytest.mark.parametrize('vfrom', ['', '', ''])
    def test_sql_version_resolve(self, vfrom):
        db = self.PartialMockDb(None, None)

        versions = ['3.0', '4.0', '4.4', '5.0', '5.1']
        M = [[None, '4.0/3.0', '4.4/3.0', None, None],
             [None, None, '4.4/4.0', '5.0/4.0', None],
             [None, None, None, '5.0/4.4', None],
             [None, None, None, None, '5.1/5.0'],
             [None, None, None, None, None]]

        assert db.sql_version_resolve(M, versions, '5.0') == ['5.1/5.0']
        assert db.sql_version_resolve(M, versions, '4.0') == [
            '5.0/4.0', '5.1/5.0']
        assert db.sql_version_resolve(M, versions, '3.0') == [
            '4.4/3.0', '5.0/4.4', '5.1/5.0']

        self.mox.VerifyAll()

    @pytest.mark.parametrize('needupdate', [True, False])
    @pytest.mark.parametrize('dryrun', [True, False])
    def test_upgrade(self, needupdate, dryrun):
        args = self.Args({'dry_run': dryrun})
        db = self.PartialMockDb(args, None)
        self.mox.StubOutWithMock(db, 'get_current_db_version')
        self.mox.StubOutWithMock(db, 'sql_version_matrix')
        self.mox.StubOutWithMock(db, 'sql_version_resolve')
        self.mox.StubOutWithMock(db, 'psql')

        versions = ['OMERO3.0__0', 'OMERO4.4__0', 'OMERO5.0__0']
        if needupdate:
            db.get_current_db_version().AndReturn(('OMERO3.0', '0'))
            db.sql_version_matrix().AndReturn(([], versions))
            db.sql_version_resolve([], versions, versions[0]).AndReturn(
                ['./sql/psql/OMERO4.4__0/OMERO3.0__0.sql',
                 './sql/psql/OMERO5.0__0/OMERO4.4__0.sql'])
            if not dryrun:
                db.psql('-f', './sql/psql/OMERO4.4__0/OMERO3.0__0.sql')
                db.psql('-f', './sql/psql/OMERO5.0__0/OMERO4.4__0.sql')
        else:
            db.get_current_db_version().AndReturn(('OMERO5.0', '0'))
            db.sql_version_matrix().AndReturn(([], versions))

        self.mox.ReplayAll()

        db.upgrade()
        self.mox.VerifyAll()

    def test_get_current_db_version(self):
        db = self.PartialMockDb(None, None)
        self.mox.StubOutWithMock(db, 'psql')

        db.psql('-c', 'SELECT currentversion, currentpatch FROM dbpatch '
                'ORDER BY id DESC LIMIT 1').AndReturn('OMERO4.4|0')
        self.mox.ReplayAll()

        assert db.get_current_db_version() == ('OMERO4.4', '0')
        self.mox.VerifyAll()

    @pytest.mark.parametrize('dbname', ['name', ''])
    def test_psql(self, dbname):
        args = self.Args({'dbhost': 'host', 'dbname': dbname,
                          'dbuser': 'user', 'dbpass': 'pass'})

        self.mox.StubOutWithMock(os.environ, 'copy')
        self.mox.StubOutWithMock(External, 'run')

        if dbname:
            os.environ.copy().AndReturn({'PGPASSWORD': 'incorrect'})
            psqlargs = ['-d', dbname, '-h', 'host', '-U', 'user',
                        '-w', '-A', '-t', 'arg1', 'arg2']
            External.run('psql', psqlargs, capturestd=True,
                         env={'PGPASSWORD': 'pass'}).AndReturn(('', ''))
        self.mox.ReplayAll()

        db = self.PartialMockDb(args, None)
        if dbname:
            db.psql('arg1', 'arg2')
        else:
            with pytest.raises(Exception) as excinfo:
                db.psql('arg1', 'arg2')
            assert str(excinfo.value) == 'Database name required'

        self.mox.VerifyAll()
