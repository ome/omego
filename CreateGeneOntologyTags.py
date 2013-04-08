from omero.gateway import BlitzGateway
import omero
from omero.rtypes import rstring

from omero.model import TagAnnotationI, AnnotationAnnotationLinkI
 
rootpassw = "ome"
host = 'localhost' # Set correct host before running.
conn = BlitzGateway('owner', rootpassw, host=host);
conn.connect()

updateService = conn.getUpdateService()


def createTag(name, description=None):
    print "Create Tag:", name
    tag = TagAnnotationI()
    tag.textValue = rstring(name)
    if description is not None:
        tag.description = rstring(description)
    return tag

def createTagGroup(name, description):
    tg = createTag(name, description)
    tg.ns = rstring("openmicroscopy.org/omero/insight/tagset")
    return tg

def createAndSaveTags(names, descriptions, tagGroup=None):
    tags = []
    for name, desc in zip(names, descriptions):
        tags.append(createTag(name, desc))
    if tagGroup is not None:
        links = []
        for t in tags:
            link = AnnotationAnnotationLinkI()
            link.parent = tagGroup
            link.child = t
            links.append(link)
        updateService.saveArray(links)
    else:
        updateService.saveArray(tags)
    print "     Saving a list of %s tags \n" % len(tags)


terms = {}      # "GO:0000002" : {'name':name, 'def': def, 'children': ['GO:00003', 'GO:00004'...], 'parents': ['GO:000045'...]}

f = open("gene_ontology.1_2.obo.txt", "r")
termId = None
name = None
desc = None
children = []
parents = []

MAX_TERM_COUNT = 10000       # There are 39,000 terms in the GO!

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
            terms[termId] = {'name':name, 'def':desc, 'parents': parents[:], 'children':[]}
            termId = None
            name = None
            parents = []
            termCount += 1
            if MAX_TERM_COUNT is not None and termCount > MAX_TERM_COUNT:
                break

count = 0
for tid, tdict in terms.items():
    print count, tid
    count += 1      # purely for display
    for p in tdict['parents']:
        if p in terms.keys():
            terms[p]['children'].append(tid)

# Get unique term IDs for Tag Groups.
tagGroups = set()
for tid, tdict in terms.items():
    print tid, tdict['children']
    # Only create Tags for GO:terms that are 'leafs' of the tree
    if len(tdict['children']) == 0:
        for p in tdict['parents']:
            tagGroups.add(p)

# Now create Tag Groups and Child Tags using data from terms dict
for pid in tagGroups:
    if pid not in terms.keys():    # In testing we may not have comeplete set
        continue
    groupData = terms[pid]
    groupName = groupData['name']
    groupDesc = groupData['def']
    tg = createTagGroup(groupName, groupDesc)
    childNames = []
    childDescs = []
    for cid in groupData['children']:
        cData = terms[cid]
        childNames.append(cData['name'])
        childDescs.append(cData['def'])
    createAndSaveTags(childNames, childDescs, tg)


f.close()
 
conn.seppuku()

# -------- IF we just want to create Tags without Tag-Groups, we can do this... ---------
# names = []
# defs = []
# f = open("gene_ontology.1_2.obo.txt", "r")
# for l in f.readlines():
#     if l.startswith("name:"):
#         names.append(l.strip()[6:])
#     elif l.startswith("def:"):
#         defs.append(l.strip()[5:])
# f.close()

# # names = names[:20]
# # defs = defs[:20]

# saveBatch = 50
# page = 0

# while((page * saveBatch) < len(names)):
#     print "PAGE: ", page, "TOTAL: ", page*saveBatch
#     start = page * saveBatch
#     stop = (page+1) * saveBatch
#     n = names[start:stop]
#     d = defs[start:stop]
#     print n
#     page += 1
#     createAndSaveTags(n, d)

# print "Created %s tags" % len(names)
