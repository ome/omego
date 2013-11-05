#!/usr/bin/env python

import getopt
import sys
import omero
import omero.cli
import os
import path
from omero.gateway import BlitzGateway
from omero.rtypes import wrap
from omero.model import DatasetI, ProjectI, ScreenI
from omero.util.import_candidates import as_dictionary

host = "localhost"
root_user = "root"
root_passw = "omero"
user_passw = "ome"

class AutoImporter:
    def __init__(self):
        self.known_users = {}
        self.orphans = "orphans"
        self.screens = "screens"
        self.no_projs = "no_projects"
        self.no_dats = "no_datasets"

    def new_connection(self, user, passw, host):
        conn = BlitzGateway(user, passw, host=host)
        conn.connect()
        return conn

    def use_connection(self, cli, host):
        sessionId = cli._event_context.sessionUuid
        conn = BlitzGateway(host=host)
        conn.connect(sUuid = sessionId)
        return conn

    def get_params(self, conn=None):
        params = omero.sys.Parameters()
        params.theFilter = omero.sys.Filter()
        if conn is not None:
            params.theFilter.ownerId = wrap(conn.getUser().getId())
        return params

    def create_containers(self, cli, project, dataset):
        """
        Creates containers with names provided if they don't exist already.
        Returns Dataset ID.
        """
        conn = self.use_connection(cli, host)
        params = self.get_params(conn)

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
        conn = self.use_connection(cli, host)
        params = self.get_params(conn)

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
                conn = self.new_connection(root_user, root_passw, host)
                params = self.get_params()
                u = conn.getObject("Experimenter", attributes={'omeName': user}, params=params)
            except Exception, e:
                print e
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
            try:
                conn.seppuku()
            except:
                pass

    def group_exists(self, user, group):
        if not self.user_exists(user):
            return False
        else:
            if group in self.known_users[user]:
                print "in Group:", group
                return True
        try:
            try:
                conn = self.new_connection(user, user_passw, host)
                groups = conn.getGroupsMemberOf()
            except Exception, e:
                print e
                return False

            if group in [g.name for g in groups]:
                print "in Group:", group
                self.known_users[user].append(group)
                return True
            else:
                print "is not in Group:", group, "- ignoring."
                return False
        finally:
            try:
                conn.seppuku()
            except:
                pass

    def do_import(self, user, group, project, dataset, archive, filename=None):
        cli = omero.cli.CLI()
        cli.loadplugins()
        cli.invoke(["login", "%s@localhost" % user, "-w", "ome", "-C"], strict=True)
        cli.invoke(["sessions", "group", group], strict=True)
        import_args = ["import"]
        if archive:
            import_args.extend(["-a"])

        if project == self.screens:
            if dataset != self.orphans:
                targetId = self.create_screen(cli, dataset)
                import_args.extend(["-r", str(targetId)])
                output = "Importing plate(s) into Screen:" + dataset
            else:
                output = "Importing plate(s) as an orphan"
        else:
            if project == self.no_projs:
                targetId = self.create_containers(cli, None, dataset)
                import_args.extend(["-d", str(targetId)])
                output = "Importing image(s) into Dataset:" + dataset
            elif dataset == self.no_dats:
                self.create_containers(cli, project, None)
                targetId = None
            elif project != self.orphans and dataset != self.orphans:
                targetId = self.create_containers(cli, project, dataset)
                import_args.extend(["-d", str(targetId)])
                output = "Importing image(s) into Project/Dataset:" + project+"/"+dataset
            else:
                output = "Importing image(s) as orphan(s)"

        if filename is not None:
            print output,
            try:
                import_args.append(filename)
                print " ...using import args", import_args
                cli.invoke(import_args, strict=True)
            except:
                print "Import failed!"
        else:
            print "No import, just container creation."

    def auto_import(self, basepath, paths, no_imports, archive):

        for filepath in paths:
            parts = filepath.strip().split(os.sep)

            # Skip commented out users - only relevant for file
            if "#" in parts:
                continue

            # Ignore relative directory paths that do not adhere to:
            # user/group/project/dataset
            # This guarantees a target but doesn't process more
            # deeply nested directories and so avoids double imports.
            if len(parts) != 4:
                #print "Ignoring ", filepath # Not that useful in general.
                continue

            print "="*100
            print "Processing ", filepath

            # Users must exist and they must be in an already existing group.
            user = parts[0]
            group = parts[1]
            if not self.group_exists(user, group):
                continue

            if no_imports:
                filepath = None
            else:
                print "-"*100
                print "Getting import canditates..."
                # If separate imports or further logging are required could use import_candidates.
                filepath = basepath.joinpath(filepath)
                import_candidates = as_dictionary([filepath])
                if len(import_candidates) == 0:
                    print "Nothing to import, path contains no import candidates."
                    # Create P/D or S anyway.
                    filepath = None

            print "-"*100

            # Finally we can import something creating containers as we go.
            self.do_import(user, group, parts[2], parts[3], archive, filepath)

        print "="*100

if __name__ == '__main__':

    try:
        opts, args = getopt.getopt(sys.argv[1:], "fna", ["file", "no_import", "archive"])
    except getopt.GetoptError as err:
        sys.exit(str(err))

    source = args[0]
    use_file = False
    no_imports = False
    archive = False
    for o, a in opts:
        if o in ("-f", "--file"):
            use_file = True
        elif o in ("-n", "--no_import"):
            no_imports = True
        elif o in ("-a", "--archive"):
            archive = True

    if use_file:
        if not os.path.exists(source):
            sys.exit('ERROR: File %s was not found!' % source)
        no_imports = True
        try:
            f = open(source, "r")
            filepaths = f.read()
            f.close()
            paths = [p for p in filepaths.split("\n")]
            basepath = None
        except:
            sys.exit('ERROR: Problem accessing file %s' % source)
    else:
        if not os.path.exists(source):
            sys.exit('ERROR: Directory %s was not found!' % source)
        basepath = path.path(source).abspath()
        paths = list(basepath.walkdirs())
        for i in range(len(paths)):
            paths[i] = str(basepath.relpathto(paths[i]))


    ai = AutoImporter()
    ai.auto_import(basepath, paths, no_imports, archive)
