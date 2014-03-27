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
from omego.framework import Stop
import omego.db
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

    @pytest.mark.parametrize('sqlexists', [True, False])
    @pytest.mark.parametrize('dryrun', [True, False])
    def test_initialise(self, sqlexists, dryrun):
        ext = self.mox.CreateMock(External)
        args = self.Args({'omerosql': 'omero.sql', 'rootpass': 'rootpass',
                          'dry_run': dryrun})
        db = self.PartialMockDb(args, ext)
        self.mox.StubOutWithMock(db, 'psql')
        self.mox.StubOutWithMock(os.path, 'exists')

        os.path.exists(args.omerosql).AndReturn(sqlexists)

        if not sqlexists and not dryrun:
            ext.omero_cli([
                'db', 'script', '-f', args.omerosql, '', '', args.rootpass])

        if not dryrun:
            db.psql('-f', args.omerosql)

        self.mox.ReplayAll()

        db.initialise()
        self.mox.VerifyAll()

    def test_sort_schema(self):
        ordered = ['OMERO3__0', 'OMERO3A__10', 'OMERO4__0', 'OMERO4.4__0',
                   'OMERO5.0__0', 'OMERO5.1DEV__0', 'OMERO5.1__0']

        ps = [5, 3, 2, 6, 0, 1, 4]
        permuted = [ordered[p] for p in ps]

        db = self.PartialMockDb(None, None)
        assert db.sort_schema(permuted) == ordered
        self.mox.VerifyAll()

    @pytest.mark.parametrize('needupdate', [True, False])
    @pytest.mark.parametrize('dryrun', [True, False])
    def test_upgrade(self, needupdate, dryrun):
        self.mox.StubOutWithMock(omego.db, 'glob')
        omego.db.glob(
            os.path.join('.', 'sql', 'psql', 'OMERO*')
            ).AndReturn(['./sql/psql/OMERO4.4__0', './sql/psql/OMERO5.0__0'])

        args = self.Args({'dry_run': dryrun})
        db = self.PartialMockDb(args, None)
        self.mox.StubOutWithMock(db, 'get_current_db_version')
        self.mox.StubOutWithMock(db, 'psql')

        if needupdate:
            db.get_current_db_version().AndReturn(('OMERO4.4', '0'))
        else:
            db.get_current_db_version().AndReturn(('OMERO5.0', '0'))

        if needupdate and not dryrun:
            db.psql('-f', './sql/psql/OMERO5.0__0/OMERO4.4__0.sql')

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

    def test_psql(self):
        args = self.Args({'dbhost': 'host', 'dbname': 'name',
                          'dbuser': 'user', 'dbpass': 'pass'})

        self.mox.StubOutWithMock(os.environ, 'copy')
        self.mox.StubOutWithMock(External, 'run')

        os.environ.copy().AndReturn({'PGPASSWORD': 'incorrect'})

        External.run('psql', [
            '-d', 'name', '-h', 'host', '-U', 'user', '-w', '-A', '-t',
            'arg1', 'arg2'], {'PGPASSWORD': 'pass'}).AndReturn(('', ''))
        self.mox.ReplayAll()

        db = self.PartialMockDb(args, None)
        db.psql('arg1', 'arg2')
        self.mox.VerifyAll()
