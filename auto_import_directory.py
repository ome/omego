#!/usr/bin/env python

import sys
import omero
import omero.cli
import os
import path
from omero.gateway import BlitzGateway
from omero.rtypes import wrap
from omero.model import DatasetI, ProjectI, ScreenI
from omero.util.import_candidates import as_dictionary

class AutoImporter:
    def __init__(self):
        self.known_users = {}
        self.orphans = "orphans"
        self.screens = "screens"
        self.no_projs = "no_projects"

    def create_containers(self, cli, project, dataset):
        """
        Creates containers with names provided if they don't exist already.
        Returns Dataset ID.
        """
        sessionId = cli._event_context.sessionUuid
        conn = BlitzGateway(host='localhost')
        conn.connect(sUuid = sessionId)
        params = omero.sys.Parameters()
        params.theFilter = omero.sys.Filter()
        params.theFilter.ownerId = wrap(conn.getUser().getId())

        d = None
        dsId = None
        if project is not None:
            # We need to find or create a project
            # This is not nice but we really shouldn't be dealing with large numbers of objects here
            plist = list(conn.getObjects("Project", attributes={'name': project}, params=params))
            if len(plist) == 0:
                # Create project and dataset then link
                p = self.create_project(conn, project)
                d = self.create_dataset(conn, dataset)
                dsId = d.id.val
                self.link_dataset(conn, p.id.val, dsId)
            else:
                # Pick the first, it's as good as any
                p = plist[0]
                print "Using existing Project:", project
                # Since Project already exists check children for dataset
                for c in p.listChildren():
                    if c.getName() == dataset:
                        d = c
                        dsId = d.getId()

                # No existing child dataset so create one and link
                if d is None:
                    d = self.create_dataset(conn, dataset)
                    dsId = d.id.val
                    self.link_dataset(conn, p.getId(), dsId)
                else:
                    print "Using existing Dataset:", dataset
        else:
            # There may be more than one dataset with the same name
            # This is not nice but we really shouldn't be dealing with large numbers of objects here
            dlist = list(conn.getObjects("Dataset", attributes={'name': dataset}, params=params))
            if len(dlist) != 0:
                # We want one without a parent, the first will do
                for c in dlist:
                    if len(c.listParents()) == 0:
                        d = c
                        dsId = d.getId()
            if d is None:
                dsId = self.create_dataset(conn, dataset).id.val
            else:
                print "Using existing Dataset:", dataset

        return dsId

    def create_project(self, conn, project):
        print "Creating new Project:", project
        p = ProjectI()
        p.name = wrap(project.encode('ascii','ignore'))
        return conn.getUpdateService().saveAndReturnObject(p)

    def create_dataset(self, conn, dataset):
        print "Creating new Dataset:", dataset
        d = DatasetI()
        d.name = wrap(dataset.encode('ascii','ignore'))
        return conn.getUpdateService().saveAndReturnObject(d)

    def link_dataset(self, conn, prId, dsId):
        print "Linking Project and Dataset..."
        link = omero.model.ProjectDatasetLinkI()
        link.parent = ProjectI(prId, False)
        link.child = DatasetI(dsId, False)
        conn.getUpdateService().saveObject(link)

    def create_screen(self, cli, screen):
        """
        Creates screen with name provided if it doesn't exist already.
        Returns Screen ID.
        """
        sessionId = cli._event_context.sessionUuid
        conn = BlitzGateway(host='localhost')
        conn.connect(sUuid = sessionId)
        params = omero.sys.Parameters()
        params.theFilter = omero.sys.Filter()
        params.theFilter.ownerId = wrap(conn.getUser().getId())

        slist = list(conn.getObjects("Screen", attributes={'name': screen}, params=params))
        if len(slist) == 0:
            print "Creating Screen:", screen
            s = ScreenI()
            s.name = wrap(screen.encode('ascii','ignore'))
            scrId = conn.getUpdateService().saveAndReturnObject(s).id.val
        else:
            scrId = slist[0].getId()
            print "Using Screen:", screen

        return scrId

    def user_exists(self, user):
        if user in self.known_users.keys():
            print "User:", user,
            return True
        try:
            try:
                conn = BlitzGateway("root", "omero", host='localhost')
                conn.connect()
                params = omero.sys.Parameters()
                params.theFilter = omero.sys.Filter()
                u = conn.getObject("Experimenter", attributes={'omeName': user}, params=params)
            except:
                print "Error getting user - ignoring."
                return False

            if u is None:
                print "User:", user, "does not exist - ignoring."
                return False
            else:
                print "User:", user,
                self.known_users[user] = []
                return True
        finally:
            conn.seppuku()

    def group_exists(self, user, group):
        if not self.user_exists(user):
            return False
        else:
            if group in self.known_users[user]:
                print "in Group:", group
                return True
        try:
            try:
                conn = BlitzGateway(user, "ome", host='localhost')
                conn.connect()
                groups = conn.getGroupsMemberOf()
            except:
                return False

            if group in [g.name for g in groups]:
                print "in Group:", group
                self.known_users[user].append(group)
                return True
            else:
                print "is not in Group:", group, "- ignoring."
                return False
        finally:
            conn.seppuku()

    def do_import(self, user, group, project, dataset, filename=None):
        cli = omero.cli.CLI()
        cli.loadplugins()
        cli.invoke(["login", "%s@localhost" % user, "-w", "ome", "-C"], strict=True)
        cli.invoke(["sessions", "group", group], strict=True)
        import_args = ["import"]

        if project == self.screens:
            if dataset != self.orphans:
                targetId = self.create_screen(cli, dataset)
                import_args.extend(["-r", str(targetId)])
                print "Importing plate(s) into Screen:", dataset
            else:
                print "Importing plate(s) as an orphan"
        else:
            if project == self.no_projs:
                targetId = self.create_containers(cli, None, dataset)
                import_args.extend(["-d", str(targetId)])
                print "Importing image(s) into Dataset:", dataset
            elif project != self.orphans and dataset != self.orphans:
                targetId = self.create_containers(cli, project, dataset)
                import_args.extend(["-d", str(targetId)])
                print "Importing image(s) into Project/Dataset:", project+"/"+dataset
            else:
                print "Importing image(s) as orphan(s)"

        if filename is not None:
            try:
                import_args.append(filename)
                print "...using import args", import_args
                cli.invoke(import_args, strict=True)
            except:
                print "Import failed!"
        else:
            print "...no import, just container creation."

    def auto_import(self, base):
        basePath = path.path(base)
        for filepath in basePath.walkdirs():
            parts = filepath.strip().split(os.sep)

            # Skip commented out users - only relevant for file
            if "#" in parts:
                continue

            # Ignore paths that do not contain adhere to:
            # scenario/user/group/project/dataset/something
            # This guarantees a target but doesn't process more
            # deeply nested directories and so avoids double imports.
            if len(parts) != 5:
                #print "Ignoring ", filepath # Not that useful in general.
                continue

            print "="*100
            print "Processing ", filepath

            # Users must exist and they must be in an already existing group.
            user = parts[1]
            group = parts[2]
            if not self.group_exists(user, group):
                continue

            print "-"*100
            print "Getting import canditates..."
            # If separate imports or further logging are required could use import_candidates.
            import_candidates = as_dictionary([filepath])
            if len(import_candidates) == 0:
                print "Nothing to import, path contains no import candidates."
                # Create P/D or S anyway.
                filepath = None

            print "-"*100

            # Finally we can import something creating containers as we go.
            self.do_import(user, group, parts[3], parts[4], filepath)

        print "="*100

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('Usage: %s directory' % sys.argv[0])

    if not os.path.exists(sys.argv[1]):
        sys.exit('ERROR: Directory %s was not found!' % sys.argv[1])

    ai = AutoImporter()
    ai.auto_import(sys.argv[1])
