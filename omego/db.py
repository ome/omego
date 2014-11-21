#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging

from glob import glob
import re

from external import External, RunException
from yaclifw.framework import Stop
from env import OmegoCommand
from env import Add, DbParser

log = logging.getLogger("omego.db")


class DbAdmin(object):

    def __init__(self, dir, command, args, external):

        self.dir = dir
        self.args = args
        log.info("%s: DbAdmin %s ...", self.__class__.__name__, dir)

        # TODO: If the server has already been configured we should use the
        # OMERO db credentials if not explicitly provided in args

        # Server directory
        if not os.path.exists(dir):
            raise Exception("%s does not exist!" % dir)

        psqlv = self.psql('--version')
        log.info('psql version: %s', psqlv)

        self.external = external

        self.check_connection()

        if command == 'init':
            self.initialise()
        elif command == 'upgrade':
            self.upgrade()
        else:
            raise Stop('Invalid db command: %s', command)

    def check_connection(self):
        try:
            self.psql('-c', '\conninfo')
        except RunException as e:
            log.error(e)
            raise Stop(30, 'Database connection check failed')

    def initialise(self):
        if not os.path.exists(self.args.omerosql):
            log.info('Creating SQL: %s', self.args.omerosql)
            if not self.args.dry_run:
                self.external.omero_cli(
                    ["db", "script", "-f", self.args.omerosql, "", "",
                     self.args.rootpass])
        else:
            log.info('Using existing SQL: %s', self.args.omerosql)

        log.info('Creating database using %s', self.args.omerosql)
        if not self.args.dry_run:
            self.psql('-f', self.args.omerosql)

    def sort_schema(self, versions):
        # E.g. OMERO3__0 OMERO3A__10 OMERO4__0 OMERO4.4__0 OMERO5.1DEV__0
        def keyfun(v):
            x = re.match(
                '.*OMERO(\d+)(\.|A)?(\d*)([A-Z]*)__(\d+)$', v).groups()
            # x3: 'DEV' should come before ''
            return (int(x[0]), x[1], int(x[2]) if x[2] else None,
                    x[3] if x[3] else 'zzz', int(x[4]))

        sortedver = sorted(versions, key=keyfun)
        return sortedver

    def sql_version_matrix(self):
        def version_pair(f):
            vto, vfrom = os.path.split(os.path.splitext(f)[0])
            vto = os.path.split(vto)[1]
            return vfrom, vto

        files = glob(os.path.join(
            self.dir, 'sql', 'psql', 'OMERO*', 'OMERO*.sql'))

        # Windows is case-insensitive, so need to ignore additional files
        # such as OMERO4.2__0/omero-4.1-*sql
        files = [f for f in files if not
                 os.path.basename(f).startswith('omero-')]

        versions = set()
        for f in files:
            versions.update(version_pair(f))
        versions = self.sort_schema(versions)
        n = len(versions)
        versionsrev = dict(vi for vi in zip(versions, xrange(n)))

        # M(from,to) = upgrade script for this pair or None
        M = [[None for b in xrange(n)] for a in xrange(n)]
        for f in files:
            vfrom, vto = version_pair(f)
            M[versionsrev[vfrom]][versionsrev[vto]] = f

        return M, versions

    def sql_version_resolve(self, M, versions, vfrom):
        def resolve_index(M, ifrom, ito):
            n = len(M)
            for p in xrange(n - 1, 0, -1):
                if M[ifrom][p]:
                    if p == ito:
                        return [M[ifrom][p]]
                    try:
                        p2 = resolve_index(M, p, ito)
                        return [M[ifrom][p]] + p2
                    except:
                        continue
            raise Exception('No upgrade path found from %s to %s' % (
                versions[ifrom], versions[ito]))

        ugpath = resolve_index(M, versions.index(vfrom), len(versions) - 1)
        return ugpath

    def upgrade(self):
        currentsqlv = '%s__%s' % self.get_current_db_version()
        M, versions = self.sql_version_matrix()
        latestsqlv = versions[-1]

        if latestsqlv == currentsqlv:
            log.info('Database is already at %s', latestsqlv)
        else:
            ugpath = self.sql_version_resolve(M, versions, currentsqlv)
            for upgradesql in ugpath:
                log.info('Upgrading database using %s', upgradesql)
                if not self.args.dry_run:
                    self.psql('-f', upgradesql)

    def get_current_db_version(self):
        q = ('SELECT currentversion, currentpatch FROM dbpatch '
             'ORDER BY id DESC LIMIT 1')
        log.debug('Executing query: %s', q)
        result = self.psql('-c', q)
        # Ignore empty string
        result = [r for r in result.split(os.linesep) if r]
        if len(result) != 1:
            raise Exception('Got %d rows, expected 1', len(result))
        v = tuple(result[0].split('|'))
        log.info('Current omero db version: %s', v)
        return v

    def psql(self, *psqlargs):
        """
        Run a psql command
        """
        if not self.args.dbname:
            raise Exception('Database name required')

        env = os.environ.copy()
        env['PGPASSWORD'] = self.args.dbpass
        args = ['-d', self.args.dbname, '-h', self.args.dbhost, '-U',
                self.args.dbuser, '-w', '-A', '-t'] + list(psqlargs)
        stdout, stderr = External.run('psql', args, capturestd=True, env=env)
        if stderr:
            log.warn('stderr: %s', stderr)
        log.debug('stdout: %s', stdout)
        return stdout


class DbCommand(OmegoCommand):
    """
    Administer an OMERO database
    """

    NAME = "db"

    def __init__(self, sub_parsers, parents):
        super(DbCommand, self).__init__(sub_parsers, parents)

        self.parser = DbParser(self.parser)
        self.parser.add_argument("-n", "--dry-run", action="store_true")

        # TODO: Kind of duplicates Upgrade args.sym/args.server
        Add(self.parser, 'serverdir', 'Root directory of the server')
        self.parser.add_argument(
            "dbcommand",
            choices=['init', 'upgrade'],
            help='Initialise or upgrade a database')

    def __call__(self, args):
        super(DbCommand, self).__call__(args)
        self.configure_logging(args)

        # Since EnvDefault.__action__ is only called if a user actively passes
        # a variable, there's no way to do the string replacing in the action
        # itself. Instead, we're post-processing them here, but this could be
        # improved.

        names = sorted(x.dest for x in self.parser._actions)
        for dest in names:
            if dest in ("help", "verbose", "quiet"):
                continue
            value = getattr(args, dest)
            if value and isinstance(value, (str, unicode)):
                replacement = value % dict(args._get_kwargs())
                log.debug("% 20s => %s" % (dest, replacement))
                setattr(args, dest, replacement)

        if args.serverdir:
            d = args.serverdir
        else:
            raise Stop(1, 'OMERO server directory required')
        ext = External(d)
        ext.setup_omero_cli()
        DbAdmin(d, args.dbcommand, args, ext)
