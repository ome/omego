#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2014 University of Dundee. All Rights Reserved.
# Use is subject to license terms supplied in LICENSE.txt
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

"""
Parser for the gene-ontology to OMERO's tag format:

[{
    "name" : "Name of the tagset",
    "desc" : "Description of the tagset",
    "set" : [{
        "name" : "Name of tag",
        "desc" : "Description of tag"
    },{
        "name" : "Name of tag",
        "desc" : "Description of tag"
    }]
}]
"""


from yaclifw.framework import Command

import logging
import json


log = logging.getLogger("omego.convert")

Example = {
    "GO:0000002": {
        'name': "name",
        'def': "defaul",
        'children': ['GO:00003', 'GO:00004'],
        'parents': ['GO:000045'],
    }
}

terms = {}


def parse(filename, MAX_TERM_COUNT=1000):
    """
    MAX_TERM_COUNT = 10000       # There are 39,000 terms in the GO!
    """
    with open(filename, "r") as f:

        termId = None
        name = None
        desc = None
        parents = []

        termCount = 0
        for l in f.readlines():
            if l.startswith("id:"):
                termId = l.strip()[4:]
            if l.startswith("name:"):
                name = l.strip()[6:]
            elif l.startswith("def:"):
                desc = l.strip()[5:]
            elif l.startswith("is_a:"):
                pid = l.strip()[6:].split(" ", 1)[0]
                parents.append(pid)
            if len(l) == 1:     # newline
                # save
                if termId is not None and name is not None:
                    terms[termId] = {'name': name, 'desc': desc,
                                     'parents': parents[:], 'children': []}
                    termId = None
                    name = None
                    parents = []
                    termCount += 1
                    if MAX_TERM_COUNT is not None and \
                       termCount > MAX_TERM_COUNT:
                        break

    count = 0
    for tid, tdict in terms.items():
        count += 1      # purely for display
        for p in tdict['parents']:
            if p in terms.keys():
                terms[p]['children'].append(tid)

    # Get unique term IDs for Tag Groups.
    tagGroups = set()
    for tid, tdict in terms.items():
        # Only create Tags for GO:terms that are 'leafs' of the tree
        if len(tdict['children']) == 0:
            for p in tdict['parents']:
                tagGroups.add(p)

    return tagGroups, terms


def generate(tagGroups, terms):
    """
    create Tag Groups and Child Tags using data from terms dict
    """

    rv = []
    for pid in tagGroups:
        # In testing we may not have complete set
        if pid not in terms.keys():
            continue

        groupData = terms[pid]
        groupName = "[%s] %s" % (pid, groupData['name'])
        groupDesc = groupData['desc']
        children = []
        group = dict(name=groupName, desc=groupDesc, set=children)
        rv.append(group)

        for cid in groupData['children']:
            cData = terms[cid]
            cName = "[%s] %s" % (cid, cData['name'])
            cDesc = cData['desc']
            child = dict(name=cName, desc=cDesc)
            children.append(child)

    return json.dumps(rv, indent=2)


class ConvertCommand(Command):
    """
    Convert between various formats
    """

    NAME = "convert"

    def __init__(self, sub_parsers):
        super(ConvertCommand, self).__init__(sub_parsers)

        self.parser.add_argument("--format", default="go", choices=["go"],
                                 help="input file format")
        self.parser.add_argument("--limit", default=1000,
                                 help="number of lines to parse")
        self.parser.add_argument("-o", "--out", default="-",
                                 help="output file. stdout by default")
        self.parser.add_argument("filename", help="input file")

    def __call__(self, args):
        super(ConvertCommand, self).__call__(args)
        self.configure_logging(args)
        tagGroups, terms = parse(args.filename, args.limit)
        print generate(tagGroups, terms)
