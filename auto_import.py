#!/usr/bin/env python

import sys
sys.path.insert(0, "/home/omero/OMERO-CURRENT/lib/python")

import omero
import omero.cli

f = open("auto_import.users", "r")
users = f.read()
f.close()
users = [x.strip().split(" ") for x in users.split("\n") if x.strip()]

f = open("auto_import.inc", "r")
files = f.read()
f.close()
files = [x.strip() for x in files.split("\n") if x.strip()]

if len(users) != len(files):
    raise Exception("Bad length %s<>%s" %(len(users), len(files)))

def do_import(user, group, filename):
    print user, group, filename
    print "-"*100
    cli = omero.cli.CLI()
    cli.loadplugins()
    cli.invoke(["login", "%s@localhost" % user, "-w", "ome", "-C"], strict=True)
    cli.invoke(["sessions", "group", group], strict=True)
    cli.invoke(["import", filename], strict=True)

for i, info in enumerate(users):

    # Skip commented out users
    if "#" in info:
        continue

    user = info[0]
    group = info[1]
    try:
        filename = info[2] # Explicit
    except IndexError:
        filename = files[i]
    do_import(user, group, filename)
    print "="*100
