# Create groups
group add private-1 --perms 'rw----'
group add read-only-1 --perms 'rwr---'
group add read-annotate-1 --perms 'rwra--'
group add read-write-1 --perms 'rwrw--'

# Create users
user add user-1 user-1 user-1 private-1 -P ome
user add user-2 user-2 user-2 private-1 read-only-1 -P ome
user add user-3 user-3 user-3 read-only-1 read-annotate-1 -P ome
user add user-4 user-4 user-4 read-only-1 read-write-1 -P ome
user add user-5 user-5 user-5 read-annotate-1 read-write-1 -P ome
user add -a user-6 user-6 user-6 private-1 read-only-1 read-annotate-1 read-write-1 -P ome
user add user-7 user-7 user-7 private-1 -P ome
user add user-8 user-8 user-8 private-1 read-only-1 -P ome
user add user-9 user-9 user-9 read-only-1 read-annotate-1 -P ome
user add user-10 user-10 user-10 read-only-1 read-write-1 -P ome
user add user-11 user-11 user-11 read-annotate-1 read-write-1 -P ome
user add -a user-12 user-12 user-12 private-1 read-only-1 read-annotate-1 read-write-1 -P ome

# Set group owners
group adduser --name private-1 user-1 user-7 --as-owner
group adduser --name read-only-1 user-3 user-9 --as-owner
group adduser --name read-annotate-1 user-5 user-11 --as-owner
group adduser --name read-write-1 user-4 user-10 --as-owner

# Create admin groups
group add adm-private-1 --perms 'rw----'
group add adm-read-only-1 --perms 'rwr---'
group add adm-read-annotate-1 --perms 'rwra--'
group add adm-read-write-1 --perms 'rwrw--'

# Create admin group users
user add user-13 user-13 user-13 adm-private-1 -P ome
user add user-14 user-14 user-14 adm-private-1 adm-read-only-1 -P ome
user add user-15 user-15 user-15 adm-read-only-1 adm-read-annotate-1 -P ome
user add user-16 user-16 user-16 adm-read-only-1 adm-read-write-1 -P ome
user add user-17 user-17 user-17 adm-read-annotate-1 adm-read-write-1 -P ome
user add -a user-18 user-18 user-18 adm-private-1 adm-read-only-1 adm-read-annotate-1 adm-read-write-1 -P ome

# Set admin group owners
group adduser --name private-1 user-13 --as-owner
group adduser --name read-only-1 user-15 --as-owner
group adduser --name read-annotate-1 user-17 --as-owner
group adduser --name read-write-1 user-16 --as-owner
