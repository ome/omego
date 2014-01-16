#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import logging

from glob import glob
import psycopg2
import re
import sys

from framework import Command, Stop
from env import EnvDefault, DbParser
from env import HOSTNAME

log = logging.getLogger("omego.db")


class DbAdmin(object):

    def __init__(self, dir, command, args):

        self.dir = dir
        self.args = args
        log.info("%s: DbAdmin %s ...", self.__class__.__name__, dir)

        # TODO: If the server has already been configured we should use the
        # OMERO db credentials if not explicitly provided in args

        # setup_script_environment() may cause the creation of a default
        # config.xml, so we must check for it here
        noconfigure = self.has_config(dir)

        # Server directory
        if not os.path.exists(dir):
            raise Exception("%s does not exist!" % dir)

        self.setup_script_environment(dir)

        # Need lib/python set above
        import path
        self.dir = path.path(dir)

        if command == 'init':
            self.initialise()
        elif command == 'upgrade':
            self.upgrade()
        else:
            raise Stop('Invalid db command: %s', command)

    def connect(self):
        conn = psycopg2.connect(
            host=self.args.dbhost, database=self.args.dbname,
            user=self.args.dbuser, password=self.args.dbpass)
        return conn

    def initialise(self):
        if not os.path.exists(self.args.omerosql):
            log.info('Creating SQL: %s', self.args.omerosql)
            self.run(
                ["db", "script", "-f", self.args.omerosql, "", "",
                 self.args.rootpass])
        else:
            log.info('Using existing SQL: %s', self.args.omerosql)

        conn = self.connect()
        with conn.cursor() as cursor:
            log.info('Creating database using %s', self.args.omerosql)
            if not self.args.dry_run:
                cursor.execute(open(self.args.omerosql, "r").read())

    def sort_schema(self, versions):
        # E.g. OMERO3__0 OMERO3A__10 OMERO4__0 OMERO4.4__0
        def keyfun(v):
            x = re.match('.*/OMERO(\d+)(\.|A)?(\d*)__(\d+)', v).groups()
            return int(x[0]), x[1], int(x[2]) if x[2] else None, x[3]

        sortedver = sorted(versions, key=keyfun)
        #log.debug(sortedver)
        return sortedver

    def upgrade(self):
        conn = self.connect()
        currentsqlv = '%s__%d' % self.get_current_db_version()
        # TODO: Is there a nicer way to get the new server DB version?
        latestsql = self.sort_schema(glob(os.path.join(
                    self.dir, 'sql', 'psql', 'OMERO*')))[-1]
        latestsqlv = os.path.basename(latestsql)

        if latestsqlv == currentsqlv:
            log.info('Database is already at %s', latestsqlv)
        else:
            upgradesql = os.path.join(latestsql, currentsqlv) + '.sql'
            with conn.cursor() as cursor:
                log.info('Upgrading database using %s', upgradesql)
                if not self.args.dry_run:
                    cursor.execute(open(upgradesql, "r").read())

    def get_current_db_version(self):
        conn = self.connect()
        with conn.cursor() as cursor:
            q = ('SELECT currentversion, currentpatch FROM dbpatch '
                 'ORDER BY id DESC LIMIT 1')
            log.debug('Executing query: %s', q)
            cursor.execute(q)
            if cursor.rowcount != 1:
                raise Exception('Got %d rows, expected 1', cursor.rowcount)
            v = cursor.fetchone()
            log.info('Current omero db version: %s', v)
            return v

    # TODO: Move this into a common class (c.f. Upgrade.run)
    def has_config(self, dir):
        log.debug(dir)
        config = os.path.join(dir, "etc", "grid", "config.xml")
        return os.path.exists(config)

    # TODO: Move this into a common class (c.f. Upgrade.run)
    def setup_script_environment(self, dir):
        dir = os.path.abspath(dir)
        lib = os.path.join(dir, "lib", "python")
        if not os.path.exists(lib):
            raise Exception("%s does not exist!" % lib)
        sys.path.insert(0, lib)

        import omero
        import omero.cli

        log.debug("Using CLI from %s", omero.cli.__file__)

        self.cli = omero.cli.CLI()
        self.cli.loadplugins()

    # TODO: Move this into a common class (c.f. Upgrade.run)
    def run(self, command):
        """
        Runs a command as if from the command-line
        without the need for using popen or subprocess
        """
        if isinstance(command, str):
            command = command.split()
        else:
            for idx, val in enumerate(command):
                command[idx] = val
        log.info("Invoking CLI [current environment]: %s", " ".join(command))
        if not self.args.dry_run:
            self.cli.invoke(command, strict=True)


class DbCommand(Command):
    """
    Administer an OMERO database
    """

    NAME = "db"

    def __init__(self, sub_parsers):
        super(DbCommand, self).__init__(sub_parsers)

        self.parser = DbParser(self.parser)
        self.parser.add_argument("-n", "--dry-run", action="store_true")

        Add = EnvDefault.add
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
        DbAdmin(d, args.dbcommand, args)
