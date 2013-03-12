from omero.gateway import BlitzGateway
import omero
from omero.rtypes import rstring
from omero_model_ProjectI import ProjectI
from omero_model_DatasetI import DatasetI
from omero_model_ProjectDatasetLinkI import ProjectDatasetLinkI
from omero_model_ExperimenterI import ExperimenterI
from omero_model_ExperimenterGroupI import ExperimenterGroupI
from omero_model_PermissionsI import PermissionsI
from omero_model_TagAnnotationI import TagAnnotationI
 
rootpassw = "omero"
host = 'localhost' # Set correct host before running.
conn = BlitzGateway('root', rootpassw, host=host);
conn.connect()
admin = conn.getAdminService()
uuid = admin.getEventContext().sessionUuid 
uuid = ""            # for real
#uuid = "_%s" % uuid   # for testing the script itself
 
userpassw = "ome"
passw = rstring(userpassw)
email = rstring("dummy@example.com")
 
groupinfo = {
    "g1":{"name":"private-1%s" % uuid, "perms":'rw----', "group":None},
    "g2":{"name":"read-only-1%s" % uuid,"perms":'rwr---', "group":None},
    "g3":{"name":"read-annotate-1%s" % uuid,"perms":'rwra--', "group":None},
    "g4":{"name":"read-write-1%s" % uuid,"perms":'rwrw--', "group":None},
    "g5":{"name":"adm-private-1%s" % uuid, "perms":'rw----', "group":None},
    "g6":{"name":"adm-read-only-1%s" % uuid,"perms":'rwr---', "group":None},
    "g7":{"name":"adm-read-annotate-1%s" % uuid,"perms":'rwra--', "group":None},
    "g8":{"name":"adm-read-write-1%s" % uuid,"perms":'rwrw--', "group":None},
}
 
userinfo = {
    "u1":{"name":"user-1%s" % uuid, "groups":["g1"], "owner":["g1"], "admin":False},
    "u2":{"name":"user-2%s" % uuid, "groups":["g1","g2"], "owner":[], "admin":False},
    "u3":{"name":"user-3%s" % uuid, "groups":["g2","g3"], "owner":["g2"], "admin":False},
    "u4":{"name":"user-4%s" % uuid, "groups":["g4","g2"], "owner":["g4"], "admin":False},
    "u5":{"name":"user-5%s" % uuid, "groups":["g3","g4"], "owner":["g3"], "admin":False},
    "u6":{"name":"user-6%s" % uuid, "groups":["g1","g2","g3","g4"], "owner":[], "admin":True},
    "u7":{"name":"user-7%s" % uuid, "groups":["g1"], "owner":["g1"], "admin":False},
    "u8":{"name":"user-8%s" % uuid, "groups":["g1","g2"], "owner":[], "admin":False},
    "u9":{"name":"user-9%s" % uuid, "groups":["g2","g3"], "owner":["g2"], "admin":False},
    "u10":{"name":"user-10%s" % uuid, "groups":["g4","g2"], "owner":["g4"], "admin":False},
    "u11":{"name":"user-11%s" % uuid, "groups":["g3","g4"], "owner":["g3"], "admin":False},
    "u12":{"name":"user-12%s" % uuid, "groups":["g1","g2","g3","g4"], "owner":[], "admin":True},
    "u13":{"name":"adm-user-1%s" % uuid, "groups":["g5"], "owner":["g5"], "admin":False},
    "u14":{"name":"adm-user-2%s" % uuid, "groups":["g5","g6"], "owner":[], "admin":False},
    "u15":{"name":"adm-user-3%s" % uuid, "groups":["g6","g7"], "owner":["g6"], "admin":False},
    "u16":{"name":"adm-user-4%s" % uuid, "groups":["g8","g6"], "owner":["g8"], "admin":False},
    "u17":{"name":"adm-user-5%s" % uuid, "groups":["g6","g8"], "owner":["g7"], "admin":False},
    "u18":{"name":"adm-user-6%s" % uuid, "groups":["g5","g6","g7","g8"], "owner":[], "admin":True},
}
 
# existing groups
userGroup = admin.lookupGroup("user")  # all users need to be in 'user' group to do anything! 
systemGroup = admin.lookupGroup("system")  # admin users need to be in 'system' group
 
####################
# Create groups
####################
 
for gno in groupinfo.keys():
    gr = conn.getObject("ExperimenterGroup", attributes={'name':groupinfo[gno]["name"]})
    if gr:
        gid = gr.getId()
        print "Group %s already exists" % groupinfo[gno]["name"]
    else:
        gr = ExperimenterGroupI()
        gr.name = rstring(groupinfo[gno]["name"])
        gr.details.permissions = PermissionsI(groupinfo[gno]["perms"])
        gid = admin.createGroup(gr)
        print "Group %s created" % groupinfo[gno]["name"]
    groupinfo[gno]["group"] = admin.getGroup(gid)
    admin.addGroups(ExperimenterI(0, False), [groupinfo[gno]["group"]])
 
for uno in userinfo.keys():
    usr = conn.getObject("Experimenter", attributes={'omeName':userinfo[uno]["name"]})
    if usr:
        uid = usr.getId()
        print "User %s already exists" % userinfo[uno]["name"]
    else:
        usr = ExperimenterI()
        usr.omeName = rstring(userinfo[uno]["name"])
        usr.firstName = rstring(userinfo[uno]["name"])
        usr.lastName = rstring(userinfo[uno]["name"])
        usr.email = email
        grps = []
        for gr in userinfo[uno]["groups"]:
            grps.append(groupinfo[gr]["group"])
        grps.append(userGroup)
        if userinfo[uno]["admin"]:
            grps.append(systemGroup)
        uid = admin.createExperimenterWithPassword(usr, passw, grps[0], grps)
        usr = admin.getExperimenter(uid)
        for gno in userinfo[uno]["owner"]:
            admin.setGroupOwner(groupinfo[gno]["group"],usr) 
        print "User %s created" % userinfo[uno]["name"]
 
conn.seppuku()