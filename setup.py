#
# setup (setup.py)
# ----------------
#
# Description:
#
#
# Author       : Nick Blundell
# Organisation : www.nickblundell.org.uk
# Version Info : $Id$
#
import ez_setup 
ez_setup.use_setuptools()
from setuptools import setup, find_packages

MAIN_PACKAGE = "rst_tex"
exec("import %s" % MAIN_PACKAGE)
VERSION = eval("%s.VERSION" % MAIN_PACKAGE)

setup(
  name = MAIN_PACKAGE,
  version = VERSION,
  packages = find_packages(),
  scripts=["scripts/rst_tex"],
  install_requires=["docutils"],
  dependency_links=["http://www.nickblundell.org.uk/packages/"],
  include_package_data=True,
)
