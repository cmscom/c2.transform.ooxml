"""Choose the format of a document and extract its text."""

from c2.transform.ooxml import logger
from c2.transform.ooxml.excel import extract_excel
from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import is_el
from c2.transform.ooxml.package import iter_xml
from c2.transform.ooxml.package import LimitReached
from c2.transform.ooxml.package import main_part
from c2.transform.ooxml.package import TextSink
from c2.transform.ooxml.powerpoint import extract_powerpoint
from c2.transform.ooxml.word import extract_word
from collections.abc import Callable
from lxml import etree

import io
import lzma
import time
import zipfile
import zlib


Extractor = Callable[[zipfile.ZipFile, str, TextSink, Budget], None]

# The root element of the main part, and the extractor of its format.
_FORMATS: tuple[tuple[str, str, Extractor], ...] = (
    ("w", "document", extract_word),
    ("s", "workbook", extract_excel),
    ("p", "presentation", extract_powerpoint),
)


def _extractor(zf: zipfile.ZipFile, main: str, budget: Budget) -> Extractor | None:
    """The extractor for the root element of the main part, or None."""
    for event, element in iter_xml(zf, main, budget):
        if event != "start":
            continue
        for ns, local, extractor in _FORMATS:
            if is_el(element, ns, local):
                return extractor
        return None
    return None


def extract_text(data: bytes, clock: Callable[[], float] = time.monotonic) -> str:
    """The text of an Office Open XML document.

    - A limit (size, parts, text, time) stops the reading: the text read so
      far is returned.
    - A file that is not a zip (a password-protected document is an OLE
      container), has no main part of a known format, or whose main part
      is broken gives no text. A broken part after the main part keeps
      the text read so far.
    Problems are logged as warnings, without the content of the document.
    """
    budget = Budget(clock=clock)
    sink = TextSink(budget)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            main = main_part(zf, budget)
            if main is None:
                logger.warning("Not an Office Open XML document: no main part")
                return ""
            extractor = _extractor(zf, main, budget)
            if extractor is None:
                logger.warning("Not an Office Open XML document of a known format")
                return ""
            extractor(zf, main, sink, budget)
    except LimitReached as limit:
        logger.warning("Text extraction stopped at a limit: %s", limit)
        return sink.text()
    except (
        zipfile.BadZipFile,
        KeyError,
        etree.XMLSyntaxError,
        ValueError,
        OSError,
        EOFError,
        # zipfile: an encrypted entry, or an unsupported compression
        # method (NotImplementedError).
        RuntimeError,
        zlib.error,
        # Corrupt LZMA data (compression method 14); corrupt bzip2 data
        # gives an OSError.
        lzma.LZMAError,
    ) as error:
        # Only the type: the message can quote the document.
        if sink.main_read:
            # A broken part after the main part (a header, a sheet, a
            # slide): keep the text read so far, as at a limit.
            logger.warning(
                "Text extraction stopped at a broken part: %s",
                type(error).__name__,
            )
            return sink.text()
        logger.warning("No text extracted: %s", type(error).__name__)
        return ""
    return sink.text()
