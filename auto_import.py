#!/usr/bin/env python

import sys
sys.path.insert(0, "/home/omero/OMERO-CURRENT/lib/python")

import omero
import omero.cli
from omero.gateway import BlitzGateway
from omero.rtypes import wrap
from omero.model import DatasetI, ProjectI

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

def create_containers(cli, dataset, project=None):
    """
    Creates containers with names provided if they don't exist already.
    Returns Dataset ID.
    """
    sessionId = cli._event_context.sessionUuid
    conn = BlitzGateway()
    conn.connect(sUuid = sessionId)
    params = omero.sys.Parameters()
    params.theFilter = omero.sys.Filter()
    params.theFilter.ownerId = wrap(conn.getUser().getId())

    d = None
    prId = None
    if project is not None:
        p = conn.getObject("Project", attributes={'name': project}, params=params)
        if p is None:
            print "Creating Project:", project
            p = omero.model.ProjectI()
            p.name = wrap(project)
            prId = conn.getUpdateService().saveAndReturnObject(p).id.val
        else:
            print "Using Project:", project, p
            prId = p.getId()
            # Since Project already exists, check children for Dataset
            for c in p.listChildren():
                if c.getName() == dataset:
                    d = c

    if d is None:
        d = conn.getObject("Dataset", attributes={'name': dataset}, params=params)

    if d is None:
        print "Creating Dataset:", dataset
        d = omero.model.DatasetI()
        d.name = wrap(dataset)
        dsId = conn.getUpdateService().saveAndReturnObject(d).id.val
        if prId is not None:
            print "Linking Project-Dataset..."
            link = omero.model.ProjectDatasetLinkI()
            link.child = omero.model.DatasetI(dsId, False)
            link.parent = omero.model.ProjectI(prId, False)
            conn.getUpdateService().saveObject(link)
    else:
        print "Using Dataset:", dataset, d
        dsId = d.getId()
    return dsId


def do_import(user, group, filename, dataset=None, project=None):
    print user, group, filename
    print "-"*100
    cli = omero.cli.CLI()
    cli.loadplugins()
    cli.invoke(["login", "%s@localhost" % user, "-w", "ome", "-C"], strict=True)
    cli.invoke(["sessions", "group", group], strict=True)
    import_args = ["import"]
    if dataset is not None:
        dsId = create_containers(cli, dataset, project)
        import_args.extend(["-d", str(dsId)])
    import_args.append(filename)
    print import_args
    cli.invoke(import_args, strict=True)

for i, info in enumerate(users):

    # Skip commented out users
    if "#" in info:
        continue

    user = info[0]
    group = info[1]
    dataset = None
    project = None

    try:
        filename = info[-1]     # Last item in the 'info' is a path ("/")
        filename.index("/")
        info.pop()
    except:
        filename = files[i]

    if len(info) > 2:
        dataset = info[-1]
        info.pop()
    if len(info) > 2:
        project = info[-1]

    filename = files[i]
    do_import(user, group, filename, dataset, project)
    print "="*100
