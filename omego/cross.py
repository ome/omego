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
            "specification",
            help='Specifies which build target to generate')

    def __call__(self, args):
        super(CrossCommand, self).__call__(args)
        self.configure_logging(args)
