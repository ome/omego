#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging

from glob import glob
import re

import fileutils
from external import External, RunException
from yaclifw.framework import Command, Stop
from env import DbParser

log = logging.getLogger("omego.db")

# Regular expression identifying a SQL schema
SQL_SCHEMA_REGEXP = re.compile('.*OMERO(\d+)(\.|A)?(\d*)([A-Z]*)__(\d+)$')

# Exit codes for db upgrade --dry-run (also used internally)
DB_UPTODATE = 0
DB_UPGRADE_NEEDED = 2
DB_INIT_NEEDED = 3


def is_schema(s):
    """Return true if the string is a valid SQL schema"""
    return SQL_SCHEMA_REGEXP.match(s) is not None


def sort_schemas(schemas):
    """Sort a list of SQL schemas in order"""
    def keyfun(v):
        x = SQL_SCHEMA_REGEXP.match(v).groups()
        # x3: 'DEV' should come before ''
        return (int(x[0]), x[1], int(x[2]) if x[2] else None,
                x[3] if x[3] else 'zzz', int(x[4]))

    return sorted(schemas, key=keyfun)


def parse_schema_files(files):
    """
    Parse a list of SQL files and return a dictionary of valid schema
    files where each key is a valid schema file and the corresponding value is
    a tuple containing the source and the target schema.
    """
    f_dict = {}
    for f in files:
        root, ext = os.path.splitext(f)
        if ext != ".sql":
            continue
        vto, vfrom = os.path.split(root)
        vto = os.path.split(vto)[1]
        if is_schema(vto) and is_schema(vfrom):
            f_dict[f] = (vfrom, vto)
    return f_dict


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

        self.external = external

        psqlv = self.psql('--version')
        log.info('psql version: %s', psqlv)

        self.check_connection()

        if command in ('init', 'upgrade', 'dump'):
            getattr(self, command)()
        elif command is not None:
            raise Stop('Invalid db command: %s', command)

    def check_connection(self):
        try:
            self.psql('-c', '\conninfo')
        except RunException as e:
            log.error(e)
            raise Stop(30, 'Database connection check failed')

    def init(self):
        omerosql = self.args.omerosql
        autoupgrade = False
        if not omerosql:
            omerosql = fileutils.timestamp_filename('omero', 'sql')
            log.info('Creating SQL: %s', omerosql)
            if not self.args.dry_run:
                self.external.omero_cli(
                    ["db", "script", "-f", omerosql, "", "",
                     self.args.rootpass])
        elif os.path.exists(omerosql):
            log.info('Using existing SQL: %s', omerosql)
            autoupgrade = True
        else:
            log.error('SQL file not found: %s', omerosql)
            raise Stop(40, 'SQL file not found')

        log.info('Creating database using %s', omerosql)
        if not self.args.dry_run:
            self.psql('-f', omerosql)

        if autoupgrade:
            self.upgrade()

    def sort_schema(self, versions):
        return sort_schemas(versions)

    def sql_version_matrix(self):
        # Parse all schema files
        files = glob(os.path.join(
            self.dir, 'sql', 'psql', 'OMERO*', 'OMERO*.sql'))
        f_dict = parse_schema_files(files)

        # Create a set of unique schema versions
        versions = set()
        for v in f_dict.values():
            versions.update(v)
        versions = sort_schemas(versions)
        n = len(versions)
        versionsrev = dict(vi for vi in zip(versions, xrange(n)))

        # M(from,to) = upgrade script for this pair or None
        M = [[None for b in xrange(n)] for a in xrange(n)]
        for key, value in f_dict.items():
            vfrom, vto = value
            M[versionsrev[vfrom]][versionsrev[vto]] = key

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

    def check(self):
        return self.upgrade(check=True)

    def upgrade(self, check=False):
        try:
            currentsqlv = '%s__%s' % self.get_current_db_version()
        except RunException as e:
            log.error(e)
            if check:
                return DB_INIT_NEEDED
            raise Stop(DB_INIT_NEEDED, 'Unable to get database version')

        M, versions = self.sql_version_matrix()
        latestsqlv = versions[-1]

        if latestsqlv == currentsqlv:
            log.info('Database is already at %s', latestsqlv)
            if check:
                return DB_UPTODATE
        else:
            ugpath = self.sql_version_resolve(M, versions, currentsqlv)
            log.debug('Database upgrade path: %s', ugpath)
            if check:
                return DB_UPGRADE_NEEDED
            if self.args.dry_run:
                raise Stop(
                    DB_UPGRADE_NEEDED, 'Database upgrade required %s->%s' % (
                        currentsqlv, latestsqlv))
            for upgradesql in ugpath:
                log.info('Upgrading database using %s', upgradesql)
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

    def dump(self):
        """
        Dump the database using the postgres custom format
        """
        dumpfile = self.args.dumpfile
        if not dumpfile:
            db, env = self.get_db_args_env()
            dumpfile = fileutils.timestamp_filename(
                'omero-database-%s' % db['name'], 'pgdump')

        log.info('Dumping database to %s', dumpfile)
        if not self.args.dry_run:
            self.pgdump('-Fc', '-f', dumpfile)

    def get_db_args_env(self):
        """
        Get a dictionary of database connection parameters, and create an
        environment for running postgres commands.
        Falls back to omego defaults.
        """
        db = {
            'name': self.args.dbname,
            'host': self.args.dbhost,
            'user': self.args.dbuser,
            'pass': self.args.dbpass
            }

        if not self.args.no_db_config:
            try:
                c = self.external.get_config(force=True)
            except Exception as e:
                log.warn('config.xml not found: %s', e)
                c = {}

            for k in db:
                try:
                    db[k] = c['omero.db.%s' % k]
                except KeyError:
                    log.info(
                        'Failed to lookup parameter omero.db.%s, using %s',
                        k, db[k])

        if not db['name']:
            raise Exception('Database name required')

        env = os.environ.copy()
        env['PGPASSWORD'] = db['pass']
        return db, env

    def psql(self, *psqlargs):
        """
        Run a psql command
        """
        db, env = self.get_db_args_env()

        args = [
            '-v', 'ON_ERROR_STOP=on',
            '-d', db['name'],
            '-h', db['host'],
            '-U', db['user'],
            '-w', '-A', '-t'
            ] + list(psqlargs)
        stdout, stderr = External.run('psql', args, capturestd=True, env=env)
        if stderr:
            log.warn('stderr: %s', stderr)
        log.debug('stdout: %s', stdout)
        return stdout

    def pgdump(self, *pgdumpargs):
        """
        Run a pg_dump command
        """
        db, env = self.get_db_args_env()

        args = ['-d', db['name'], '-h', db['host'], '-U', db['user'], '-w'
                ] + list(pgdumpargs)
        stdout, stderr = External.run(
            'pg_dump', args, capturestd=True, env=env)
        if stderr:
            log.warn('stderr: %s', stderr)
        log.debug('stdout: %s', stdout)
        return stdout


class DbCommand(Command):
    """
    Administer an OMERO database
    """

    NAME = "db"

    def __init__(self, sub_parsers):
        super(DbCommand, self).__init__(sub_parsers)

        self.parser = DbParser(self.parser)
        self.parser.add_argument("-n", "--dry-run", action="store_true", help=(
            "Simulation/check mode. In 'upgrade' mode exits with code 2 if an "
            "upgrade is required, 3 if database isn't initialised, 0 if "
            "database is up-to-date."))

        # TODO: Kind of duplicates Upgrade args.sym/args.server
        self.parser.add_argument(
            '--serverdir', help='Root directory of the server')
        self.parser.add_argument(
            "dbcommand",
            choices=['init', 'upgrade', 'dump'],
            help='Initialise or upgrade a database')
        self.parser.add_argument('--dumpfile', help='Database dump file')

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
            if value and isinstance(value, basestring):
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
