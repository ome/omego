#!/usr/bin/env python

import omero
import omero.cli
from omero.gateway import BlitzGateway
from omero.rtypes import wrap, rlong, rdouble, rint, rstring
from omero.model import DatasetI, ProjectI, TagAnnotationI

# Only these people will be logged in to do Tagging, Comments etc 
# We will still create Tags for ALL users so they're available for others to use.

USER_NAMES = ["user-10", "user-11", "user-12"]
# USER_NAMES = ["user-7", "user-8", "user-9", "user-10", "user-11", "user-12"]



conn = BlitzGateway('root', 'omero', host='localhost')
conn.connect()

conn.SERVICE_OPTS.setOmeroGroup(-1)


# ---- CONFIGURATION ----
TAG_COUNT = 1       # Number of tags each user should use (link)
TAG_TARGETS = ['Project', 'Dataset', 'Image', "Screen", "Plate"]
ROI_COUNT = 3

allUsers = []
for exp in conn.getObjects("Experimenter"):
    n = exp.getName()
    if n not in ["root", "guest"]:
        print n
        allUsers.append(exp)


def addRect(roi, x=10, y=10, w=100, h=50, theZ=0, theT=0, label=None):
    """ create and save a rectangle shape, add it to roi """
    rect = omero.model.RectI()
    rect.x = rdouble(x)
    rect.y = rdouble(y)
    rect.width = rdouble(w)
    rect.height = rdouble(h)
    if theZ is not None:
        rect.theZ = rint(theZ)
    if theT is not None:
        rect.theT = rint(theT)
    if label is not None:
        rect.textValue = wrap(label)
    rect.setRoi(roi)
    roi.addShape(rect)


# First, we want to make sure that every user has a tag(s) in every group
print "\n---- CREATING TAGS ----\n"
for exp in allUsers:
    username = exp.getOmeName()
    print username
    userConn = BlitzGateway(username, "ome")
    userConn.connect()
    for g in userConn.getGroupsMemberOf():
        if g.getName() == "user":
            continue
        print " ", g.getName()
        userConn.SERVICE_OPTS.setOmeroGroup(g.getId())
        params = omero.sys.Parameters()
        params.theFilter = omero.sys.Filter()
        params.theFilter.ownerId = rlong(exp.getId())
        tags = list( userConn.getObjects("TagAnnotation", params=params) )
        for i in range( TAG_COUNT-len(tags) ):
            t = TagAnnotationI()
            newTagVal = "%s_%s_TEST" % (username, g.getName())
            print "creating TAG:", newTagVal
            t.textValue = wrap(str(newTagVal))
            userConn.getUpdateService().saveObject(t, userConn.SERVICE_OPTS)
        # for t in tags:
        #     print "    TAG", t.getId(), t.getTextValue()
    userConn.c.closeSession()



print "\n---- DOING ANNOTATING... ----\n"
# We want to Tag loads of stuff with OUR tags and Others' tags
for exp in allUsers:
    username = exp.getOmeName()
    if username not in USER_NAMES:
        continue
    print "\n\n------------ USER:", exp.getId(), username, "------------"
    userConn = BlitzGateway(username, "ome")
    userConn.connect()
    updateService = userConn.getUpdateService()
    for g in userConn.getGroupsMemberOf():
        if g.getName() == "user":
            continue
        print "\n -- GROUP:", g.getName(), "(%s adding annotations)" % username
        userConn.SERVICE_OPTS.setOmeroGroup(g.getId())

        # Get list of users in group:
        groupUsers = list( userConn.containedExperimenters(g.id) )

        p = omero.sys.Parameters()
        p.theFilter = omero.sys.Filter()
        # p.theFilter.limit = wrap(TAG_COUNT)
        # p.theFilter.ownerId = rlong(exp.getId())

        # Get Tags for ALL users in the group.
        tags = list( userConn.getObjects("TagAnnotation") )
        print " - Using TAGS:"
        for t in tags:
            print '   ', t.getTextValue()


        # data from each user (including ME)
        for user in groupUsers:
            print "--- ANNOTATING data for USER: %s ---" % user.getOmeName()
            p.theFilter.ownerId = rlong(user.id)
            for dtype in TAG_TARGETS:
                if dtype == "Plate":   # Workaround for Bug: #10519
                    plates = list( userConn.getObjects(dtype) )
                    dataObjs = [plate for plate in plates if plate.details.owner.id.val == user.id]
                else:
                    dataObjs = list( userConn.getObjects(dtype, params=p))   # Projects, Datasets etc.
                print " --> DATA: ", dataObjs
                for d in dataObjs:
                    print "  -", dtype, d.getId(), d.name, d.details.owner.id.val, "canAnnotate()", d.canAnnotate(), "canLink()", d.canLink()
                    if d.canAnnotate():
                        # --- ADD TAGS ---
                        for t in tags:
                            if t.canAnnotate():
                                # Check if this user has already added Tag
                                #if (len( list(userConn.getAnnotationLinks(dtype, parent_ids=[d.getId()], ann_ids=[t.getId()], params=p)) )==0):
                                try:
                                    d.linkAnnotation(t, sameOwner=False)
                                    print " ** TAG added: %s **" % t.getTextValue()
                                except:
                                    print "  ********* ERROR adding Tag! ***********"
                                    pass
                                #else:
                                #    print " - Tag '%s' already added -"  % t.getTextValue()
                            else:
                                print " - Can't Annotate using Tag '%s' -"  % t.getTextValue()
                        # --- ADD COMMENTS ---
                        cTxt = str("Comment Added by %s" % exp.getOmeName())
                        print " ** COMMENT added to %s **" % dtype
                        comment = omero.gateway.CommentAnnotationWrapper()
                        comment.setValue(cTxt)
                        d.linkAnnotation(comment, sameOwner=False)
                        # --- ADD ROIS ---
                        if dtype == "Image":
                            for r in range(ROI_COUNT):
                                print " ** ROI added to Image:", d.getId(), d.getName()
                                roi = omero.model.RoiI()
                                roi.setImage(d._obj)
                                x = (r * 10) + 10;
                                addRect(roi, x=x, y=x, label=str("Added by %s" % exp.getOmeName()))
                                if d.getSizeZ() > 1:
                                    addRect(roi, x=x, y=x, theZ=1, label=str("Added by %s" % exp.getOmeName()))
                                updateService.saveObject(roi, userConn.SERVICE_OPTS)
                        # --- ADD DATASETS to Projects ---
                    # if dtype == "Project" and d.canLink():
                    #     print " ** DATASET added to Project..."
                    #     dataset = omero.model.DatasetI()
                    #     dataset.name = rstring(str("%s-%s_TEST" % (exp.getOmeName(), g.getName())))
                    #     link = omero.model.ProjectDatasetLinkI()
                    #     link.parent = d._obj
                    #     link.child = dataset
                    #     updateService.saveObject(link, userConn.SERVICE_OPTS)
    # Clean-up conn for each user
    userConn.c.closeSession()
