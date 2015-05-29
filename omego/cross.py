#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging

from glob import glob
import re

import fileutils
from external import External, RunException
from yaclifw.framework import Command, Stop
from env import EnvDefault, DbParser

log = logging.getLogger("omego.x")


class CrossCommand(Command):
    """
    Build-generation command for producing a cross-product
    of various OMERO requirements.
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
            nargs="+",
            help='Specifies which build target to generate')

    def __call__(self, args):
        super(CrossCommand, self).__call__(args)
        self.configure_logging(args)

        builds = set()
        specs = list(args.spec)
        for spec in specs:
            if spec == "*":
                self.log.debug("Building all...")
            elif spec == "?":
                self.log.debug("Building random...")
            elif spec.startswith("B"):
                self.log.debug("Building base spec...")
            elif spec.startswith("S"):
                self.log.debug("Building server spec...")
