OMEGO version history
=====================

0.7.0 (November 2019)
---------------------

* Add Python 3 support in omego (#122)
* Add support for OMERO bundles without embedded lib/python (#126)
* Add --ci aliases and fix the --ci/--branch semantics (#121, #123)
* Run integration tests on Ice 3.6 (#116, #120)


0.6.5 (December 2017)
---------------------

* Fix version sourcing and make the package zip-safe (#114)

0.6.4 (August 2017)
-------------------

* Add support for passing CI build numbers (#111)

0.6.3 (July 2017)
-----------------

* Do not check database if ``--managedb`` is not set (#108)

0.6.2 (June 2017)
-----------------

* Simplify install and upgrade commands and introduce ``-managedb`` flag (#107)

0.6.1 (June 2017)
------------------

* Refactor the database management logic (#104)

0.6.0 (April 2017)
------------------

* Fix artifacts retrieval for OMERO 5.3.0 and above (#101)

Breaking changes:

* When retrieving artifacts using a custom downloads server, the OMERO
  artifacts are now expected to be stored under a URL of type
  `DOWNLOADS_URL/omero/VERSION/artifacts`

0.5.0 (March 2017)
------------------

* Symlink downloaded artifacts (#97)

Breaking changes:

* Change the default server symlink from OMERO-CURRENT to OMERO.server

0.4.1 (June 2016)
-----------------

* Fix Travis build
* Add reference to pypi distribution to the top-level README
* Refactor the SQL schema files parsing and sorting logic
* Add protocol support to the `--ci` argument

0.4.0 (May 2016)
----------------

Add `--ice` argument. With the introduction of Ice
3.6 support in OMERO 5.2.3, some applications
began getting Ice 3.6 artifacts unintentionally.
Now the choice is explicit.

0.3.0 (February 2016)
---------------------

First large refactoring which reduces
support for OMERO 5.1 and earlier though
upgrading a 5.0 server is still possible.

* remove `--ports` support in favor of 5.2 properties
* add `omero db dump`
* add `no-start` option
* add `--upgradedb` for omego install
* convert boolean string args to flags

0.2.5 (August 2015)
-------------------

* archive logs before upgrade
* upgrade DB fixes
* download insight rather than clients

0.2.4 (December 2014)
---------------------

* change `--cfg` to `--prestartfile`

0.2.3 (September 2014)
----------------------

Fix db patch issue

0.2.2 (June 2014)
-----------------

More yaclifw bug fixes

0.2.1 (June 2014)
-----------------

Minor bug fix after migration to yaclifw

0.2.0 (June 2014)
-----------------

Migrate to use of https://github.com/openmicroscopy/yaclifw

0.1.3 (April 2014)
------------------

First release with new name "omego"
