"""
Packaging instructions
"""
import jme.drs
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

DESCRIPTION = "Snakemake includes for picking up remote files"
LONG_DESCRIPTION = jme.drs.__doc__
NAME = "dynamic_remote_snake"
AUTHOR = "John Eppley"
AUTHOR_EMAIL = "jmeppley@hawaii.edu"
MAINTAINER = "John Eppley"
MAINTAINER_EMAIL = "jmeppley@hawaii.edu"
DOWNLOAD_URL = 'http://github.com/jmeppley/dynamic_remote_snake'
LICENSE = 'GPL'
VERSION = jme.drs.__version__

setup(name=NAME,
      version=VERSION,
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      maintainer=MAINTAINER,
      maintainer_email=MAINTAINER_EMAIL,
      url=DOWNLOAD_URL,
      download_url=DOWNLOAD_URL,
      license=LICENSE,
      packages=['jme.drs', ],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GPL License',
          'Natural Language :: English',
          'Programming Language :: Python :: 3.7'],
      )
