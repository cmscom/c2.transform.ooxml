"""The transform from Office Open XML documents to plain text."""

from c2.transform.ooxml import logger
from c2.transform.ooxml.config import ooxml_mimetypes
from c2.transform.ooxml.config import SITE_CHARSET
from c2.transform.ooxml.config import TRANSFORM_NAME
from c2.transform.ooxml.extract import extract_text
from Products.PortalTransforms.data import datastream
from Products.PortalTransforms.interfaces import ITransform
from zope.interface import implementer


@implementer(ITransform)
class ooxml_to_text:
    __name__ = TRANSFORM_NAME

    inputs = tuple(m["mimetypes"][0] for m in ooxml_mimetypes)

    output = "text/plain"

    output_encoding = SITE_CHARSET

    def __init__(self, name: str | None = None) -> None:
        if name:
            self.__name__ = name

    def name(self) -> str:
        return self.__name__

    def convert(
        self, orig: bytes | str, data: datastream, **kwargs: object
    ) -> datastream:
        """Set the text of ``orig`` (bytes) on ``data``.

        ``data`` is the datastream that portal_transforms made for the result.
        On any failure the text is empty, so saving the file still works.
        """
        if not isinstance(orig, bytes):
            logger.warning(
                "ooxml_to_text expects bytes, got %s; no text is extracted",
                type(orig).__name__,
            )
            data.setData("")
            return data
        data.setData(extract_text(orig))
        return data


def register() -> ooxml_to_text:
    return ooxml_to_text()
