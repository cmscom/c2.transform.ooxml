"""The text of Word documents (docx, dotx, docm, dotm)."""

from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import is_el
from c2.transform.ooxml.package import iter_xml
from c2.transform.ooxml.package import relationships
from c2.transform.ooxml.package import TextSink
from lxml import etree

import zipfile


# The parts after the body, in this order. Comments are not read.
_AFTER_BODY = (("header", "footer"), ("footnotes",), ("endnotes",))


def _in_run(element: etree._Element) -> bool:
    parent = element.getparent()
    return parent is not None and is_el(parent, "w", "r")


def _write_part(zf: zipfile.ZipFile, name: str, sink: TextSink, budget: Budget) -> None:
    """Write the text of one part.

    - The text of ``w:t``; ``w:tab`` is a tab, ``w:br`` and ``w:cr`` are
      line breaks, and every paragraph ends with a line break.
    - Inserted text (``w:ins``) is text of the document; deleted text
      (``w:delText``) and field instructions (``w:instrText``) are not.
    - ``mc:Fallback`` repeats the content of ``mc:Choice`` (for example a
      text box), so it is skipped. So is ``w:moveFrom``, the old place of
      text moved with tracked changes (it is written at ``w:moveTo``).
    """
    skipping = 0
    for event, element in iter_xml(zf, name, budget):
        if is_el(element, "mc", "Fallback") or is_el(element, "w", "moveFrom"):
            skipping += 1 if event == "start" else -1
            continue
        if event != "end" or skipping:
            continue
        if is_el(element, "w", "t"):
            sink.write(element.text or "")
        elif is_el(element, "w", "tab") and _in_run(element):
            sink.write("\t")
        elif (
            (is_el(element, "w", "br") or is_el(element, "w", "cr"))
            and _in_run(element)
        ) or is_el(element, "w", "p"):
            sink.write("\n")


def extract_word(
    zf: zipfile.ZipFile, main: str, sink: TextSink, budget: Budget
) -> None:
    """Write the text of the body, then of the headers and footers (in the
    order of their relationships), the footnotes and the endnotes."""
    _write_part(zf, main, sink, budget)
    rels = relationships(zf, main, budget)
    for kinds in _AFTER_BODY:
        for rel in rels:
            if rel.kind in kinds:
                _write_part(zf, rel.target, sink, budget)
