Usage:

auto_import_directory.py [-a | --archive] [-f | --file] [-n | --no-imports] target

 -a, -archive
	archive any actual imports

 -f, --file
	specified target is a text file used for P/D and S creation only,
	otherwise target is a directory

 -n, --no-imports
	do not import even if the target is a directory

Directory
---------

A nested structure, optionally containing images and screens, (rsynced) is created with
information about the user, group and destination using this restricted format:

 * Images to be imported into a Project/Dataset:
	import-scenario/user-name/group-name/project-name/dataset-name/images

 * Images to be imported into a Dataset not within a Project:
	import-scenario/user-name/group-name/"no_projects"/dataset-name/images

 * Images to be imported as orphans:
	import-scenario/user-name/group-name/"orphans"/"orphans"/images

 * Plates to be imported into a Screen:
	import-scenario/user-name/group-name/"screens"/screen-name/plates

 * Plates to be imported as orphans:
	import-scenario/user-name/group-name/"screens"/"orphans"/plates

For this stage we insist the user and group exists (this could be relaxed)
  * if the first directory does not correspond to a user it is ignored,
  * if the second directory does not correspond to a group of that user it is ignored.

If a directory is valid but contains no images or plates the containers will be created.

Example, two import scenarios:

import-scenario-1/user-1/private-1/no-projects/User-1-Gr-P-Dat1-TEST/
import-scenario-1/user-1/private-1/User-1-Gr-P-Pro1-TEST/User-1-Gr-P-Dat2-TEST/
import-scenario-1/user-7/private-1/screens/User-7-Gr-P-Scr1-TEST/
import-scenario-1/user-7/private-1/User-7-Gr-P-Pro1-TEST/User-7-Gr-P-Dat2-TEST/
import-scenario-1/user-2/private-1/screens/User-2-Gr-P-Scr1-TEST/
import-scenario-1/user-2/read-only-1/no-projects/User-2-Gr-RO-Dat1-TEST/
import-scenario-1/user-2/read-only-1/orphans/orphans/
import-scenario-1/user-2/read-only-1/screens/orphans/

import-scenario-2/user-2/private-1/User-2-Gr-P-Pro1-TEST/User-2-Gr-P-Dat2-TEST/
import-scenario-2/user-2/read-only-1/User-2-Gr-RO-Pro1-TEST/User-2-Gr-RO-Dat2-TEST/

Then something like:

create_users
auto_import_directory.py import-scenario-1
auto_import_directory.py -a import-scenario-2

will import the images and plates creating containers as necessary.

Alternatively,

create_users
auto_import_directory.py --no-imports import-scenario-1
auto_import_directory.py -n import-scenario-2

will create the relevant containers but to undertake no imports.


File
----

A file reflecting the above structure with one entry per line.

Example, two import scenarios:

import-scenario-1.txt contains:
user-1/private-1/no-projects/User-1-Gr-P-Dat1-TEST/
user-1/private-1/User-1-Gr-P-Pro1-TEST/User-1-Gr-P-Dat2-TEST/
user-7/private-1/screens/User-7-Gr-P-Scr1-TEST/
user-7/private-1/User-7-Gr-P-Pro1-TEST/User-7-Gr-P-Dat2-TEST/
user-2/private-1/screens/User-2-Gr-P-Scr1-TEST/
user-2/read-only-1/no-projects/User-2-Gr-RO-Dat1-TEST/

import-scenario-2.txt contains:
user-2/private-1/User-2-Gr-P-Pro1-TEST/User-2-Gr-P-Dat2-TEST/
user-2/read-only-1/User-2-Gr-RO-Pro1-TEST/User-2-Gr-RO-Dat2-TEST/

Then something like:

create_users
auto_import_directory.py -f import-scenario-1.txt
auto_import_directory.py --file import-scenario-2.txt

will create the relevant containers but to undertake no imports.

Notes
-----

There might be some care needed with creation of datasets etc simultaneously for the same user/group.

This directory structure will eventually become some sort of DropBox template once it can handle the P/D and S creation in this way.
