"""The text of PowerPoint presentations (pptx, potx, ppsx, pptm, potm, ppsm)."""

from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import is_el
from c2.transform.ooxml.package import iter_xml
from c2.transform.ooxml.package import r_id
from c2.transform.ooxml.package import relationships
from c2.transform.ooxml.package import TextSink

import zipfile


def _slide_ids(zf: zipfile.ZipFile, main: str, budget: Budget) -> list[str]:
    """The ``r:id`` of the slides, hidden ones too, in the presentation order."""
    ids = []
    for event, element in iter_xml(zf, main, budget):
        if event == "start" and is_el(element, "p", "sldId"):
            rel_id = r_id(element)
            if rel_id is not None:
                ids.append(rel_id)
    return ids


def _write_part(zf: zipfile.ZipFile, name: str, sink: TextSink, budget: Budget) -> None:
    """Write the text of ``a:t``; ``a:br`` is a line break and every
    paragraph ends with one. ``mc:Fallback`` repeats ``mc:Choice`` and is
    skipped."""
    skipping = 0
    for event, element in iter_xml(zf, name, budget):
        if is_el(element, "mc", "Fallback"):
            skipping += 1 if event == "start" else -1
            continue
        if event != "end" or skipping:
            continue
        if is_el(element, "a", "t"):
            sink.write(element.text or "")
        elif is_el(element, "a", "br") or is_el(element, "a", "p"):
            sink.write("\n")


def extract_powerpoint(
    zf: zipfile.ZipFile, main: str, sink: TextSink, budget: Budget
) -> None:
    """Write the text of each slide, then of its notes. Comments are not read."""
    slide_ids = _slide_ids(zf, main, budget)
    sink.main_read = True
    targets = {rel.rel_id: rel.target for rel in relationships(zf, main, budget)}
    for rel_id in slide_ids:
        slide = targets.get(rel_id)
        if slide is None:
            continue
        _write_part(zf, slide, sink, budget)
        for rel in relationships(zf, slide, budget):
            if rel.kind == "notesSlide":
                _write_part(zf, rel.target, sink, budget)
