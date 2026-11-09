"""Make Office Open XML files searchable in Plone."""

# Importing config registers the OOXML types with the mimetypes module.
from c2.transform.ooxml import config  # noqa: F401

from importlib.metadata import version

import logging


PACKAGE_NAME = "c2.transform.ooxml"

# The version is kept only in pyproject.toml, where the release workflow
# changes it.
__version__ = version(PACKAGE_NAME)

logger = logging.getLogger(PACKAGE_NAME)
