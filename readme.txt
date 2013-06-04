A nested structure containing images and screens (rsynced) is created with
information about the user, group and destination using this restricted format:

 * Images to be imported into a Project/Dataset:
scenario/user-name/group-name/project-name/dataset-name/images

 * Images to be imported into a Dataset not within a Project:
scenario/user-name/group-name/"no_projects"/dataset-name/images

 * Images to be imported as orphans:
scenario/user-name/group-name/"orphans"/"orphans"/images

 * Plates to be imported into a Screen:
scenario/user-name/group-name/"screens"/screen-name/plates

 * Plates to be imported as orphans:
scenario/user-name/group-name/"screens"/"orphans"/plates

For this stage we insist the user and group exists (this could be relaxed)
  * if the first directory does not correspond to a user it is ignored
  * if the second directory does not correspond to a group of that user it is ignored


Example, two import scenarios:

import-scenario-1/user-1/private-1/no-projects/User-1-Gr-P-Dat1-TEST/
import-scenario-1/user-1/private-1/User-1-Gr-P-Pro1-TEST/User-1-Gr-P-Dat2-TEST/
import-scenario-1/user-7/private-1/screens/User-7-Gr-P-Scr1-TEST/
import-scenario-1/user-7/private-1/User-7-Gr-P-Pro1-TEST/User-7-Gr-P-Dat2-TEST/
import-scenario-1/user-2/private-1/screens/User-2-Gr-P-Scr1-TEST/
import-scenario-1/user-2/read-only-1/no-projects/User-2-Gr-RO-Dat1-TEST/
import-scenario-1/user-2/read-only-1/orphans/orphans/
import-scenario-1/user-2/read-only-1/screens/orphans/

scenario-2/user-2/private-1/User-2-Gr-P-Pro1-TEST/User-2-Gr-P-Dat2-TEST/
scenario-2/user-2/read-only-1/User-2-Gr-RO-Pro1-TEST/User-2-Gr-RO-Dat2-TEST/

Then something like:

create_users
auto_import_directory.py import-scenario-1
auto_import_directory.py import-scenario-2


could be used. 

Notes:

There might be some care needed with creation of datasets etc simultaneously for the same user/group.

This structure will eventually become some sort of DropBox template once it can handle the P/D and S creation in this way.

Additionally the structure could be represented as a straight text file or just used for P/D & S creation, e.g.,

auto_import_directory.py --file import-scenario-1.txt 
auto_import_directory.py import-scenario-1 --no-imports
