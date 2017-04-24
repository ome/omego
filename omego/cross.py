#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging

from glob import glob
import re

import fileutils
import itertools
import random

from external import External, RunException
from yaclifw.framework import Command, Stop
from env import EnvDefault, DbParser

log = logging.getLogger("omego.x")


class BadSpec(Exception):

    def __init__(self, spec):
        self.spec = spec
        super(Exception, self).__init__("Bad spec: %s" % spec)

class Base(object):

    def __init__(self, name):
        self.errors = 0
        self.value = self.VALUES.get(name, "UNKNOWN")
        if self.value == "UNKNOWN":
            self.errors += 1

    def __str__(self):
        return self.value


class Platform(Base):

    VALUES = {
        "c": "centos6",
        "C": "centos7",
        "u": "ubuntu1404",
        "U": "ubuntu1504",
    }


class Python(Base):

    VALUES = {
        "p": "python2.6",
        "P": "python2.7",
    }


class Web(Base):

    VALUES = {
        "n": "nginx",
        "N": "nginx",
        "a": "apache2.2",
        "A": "apache2.4",
    }


class Postgres(Base):

    VALUES = {
        "p": "postgres9.2",
        "P": "postgres9.4",
    }


class Java(Base):

    VALUES = {
        "j": "jdk7",
        "J": "jdk8",
    }


class Spec(object):

    def __init__(self, spec):
        if len(spec) != 5:
            raise BadSpec(spec)

        self.platform = Platform(spec[0])
        self.python = Python(spec[1])
        self.web = Web(spec[2])
        self.postgres = Postgres(spec[3])
        self.java = Java(spec[4])
        self.errors = 0
        for x in self.foreach():
            self.errors += x.errors

    def foreach(self):
        yield self.platform
        yield self.python
        yield self.web
        yield self.postgres
        yield self.java

    def __str__(self):
        return "%s-%s-%s-%s-%s" % tuple(self.foreach())


class CrossCommand(Command):
    """
    Build-generation command for producing a cross-product
    of various OMERO requirements.

    Examples:

        cpnpj - minimal support CentOS6 configuration
        CPNPJ - maximal suppoer CentOS7 configuration

    """

    NAME = "x"

    def __init__(self, sub_parsers):
        super(CrossCommand, self).__init__(sub_parsers)

        self.parser.add_argument(
            "-n", "--dry-run",
            action="store_true",
            help='Print all builds and exit')
        self.parser.add_argument(
            "-d", "--describe",
            action="store_true",
            help='Print all builds with explanations and exit')
        self.parser.add_argument(
            "--output",
            help='Choose an output directory')
        self.parser.add_argument(
            "--overwrite",
            help='Permit overwriting existing files')
        self.parser.add_argument(
            "spec",
            default=("?",),
            help='Specifies which build target to generate')

    def forall(self):
        for k in itertools.product(
            Platform.VALUES.keys(),
            Python.VALUES.keys(),
            Web.VALUES.keys(),
            Postgres.VALUES.keys(),
            Java.VALUES.keys()):
            yield "".join(k)

    def __call__(self, args):
        super(CrossCommand, self).__call__(args)
        self.configure_logging(args)

        builds = set()
        spec = str(args.spec)
        if spec == "*":
            self.log.debug("Building all...")
            for spec in self.forall():
                print Spec(spec)
        elif spec == "?":
            self.log.debug("Building random...")
            spec = random.choice(list(self.forall()))
            print Spec(spec)
        elif spec.startswith("B"):
            self.log.debug("Building base spec...")
        elif spec.startswith("S"):
            self.log.debug("Building server spec...")
        else:
            print Spec(spec)
