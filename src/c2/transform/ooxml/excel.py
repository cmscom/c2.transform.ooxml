"""The text of Excel workbooks (xlsx, xltx, xlsm, xltm)."""

from c2.transform.ooxml import config
from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import is_el
from c2.transform.ooxml.package import iter_xml
from c2.transform.ooxml.package import LimitReached
from c2.transform.ooxml.package import r_id
from c2.transform.ooxml.package import relationships
from c2.transform.ooxml.package import TextSink

import zipfile


def _sheets(
    zf: zipfile.ZipFile, main: str, budget: Budget
) -> list[tuple[str, str | None]]:
    """(name, r:id) of every sheet, hidden ones too, in the workbook order."""
    return [
        (element.get("name") or "", r_id(element))
        for event, element in iter_xml(zf, main, budget)
        if event == "start" and is_el(element, "s", "sheet")
    ]


def _shared_strings(zf: zipfile.ZipFile, name: str, budget: Budget) -> list[str]:
    """The shared strings. The phonetic reading (``s:rPh``) is left out.

    They count toward the limit of the text, as they are kept in memory.
    """
    strings: list[str] = []
    current: list[str] = []
    phonetic = 0
    total = 0
    for event, element in iter_xml(zf, name, budget):
        if is_el(element, "s", "rPh"):
            phonetic += 1 if event == "start" else -1
            continue
        if event != "end":
            continue
        if is_el(element, "s", "t") and not phonetic:
            current.append(element.text or "")
        elif is_el(element, "s", "si"):
            text = "".join(current)
            current = []
            total += len(text)
            if total > config.MAX_TEXT_CHARS:
                raise LimitReached(
                    f"text length of the shared strings ({config.MAX_TEXT_CHARS})"
                )
            strings.append(text)
    return strings


def _shared(strings: list[str], value: str) -> str | None:
    try:
        index = int(value)
    except ValueError:
        return None
    if 0 <= index < len(strings):
        return strings[index]
    return None


def _write_sheet(
    zf: zipfile.ZipFile,
    name: str,
    strings: list[str],
    sink: TextSink,
    budget: Budget,
) -> None:
    """Write each row as one line, its cell values separated by tabs.

    The value of a cell is the value saved with it (``s:v``, the result of
    a formula; dates stay numbers) or its inline string; formulas are not
    written, and a cell without a value is left out.
    """
    row: list[str] = []
    cell_type: str | None = None
    value: str | None = None
    inline: list[str] = []
    phonetic = 0
    for event, element in iter_xml(zf, name, budget):
        if is_el(element, "s", "rPh"):
            phonetic += 1 if event == "start" else -1
            continue
        if event == "start":
            if is_el(element, "s", "row"):
                row = []
            elif is_el(element, "s", "c"):
                cell_type = element.get("t")
                value = None
                inline = []
            continue
        if is_el(element, "s", "v"):
            value = element.text or ""
        elif is_el(element, "s", "t") and not phonetic:
            inline.append(element.text or "")
        elif is_el(element, "s", "c"):
            if cell_type == "inlineStr":
                row.append("".join(inline))
            elif cell_type == "s":
                text = _shared(strings, value or "")
                if text is not None:
                    row.append(text)
            elif value is not None:
                row.append(value)
        elif is_el(element, "s", "row"):
            sink.write("\t".join(row) + "\n")


def extract_excel(
    zf: zipfile.ZipFile, main: str, sink: TextSink, budget: Budget
) -> None:
    """Write the name of each sheet on a line, then its rows."""
    sheets = _sheets(zf, main, budget)
    rels = relationships(zf, main, budget)
    targets = {rel.rel_id: rel.target for rel in rels}
    strings: list[str] = []
    for rel in rels:
        if rel.kind == "sharedStrings":
            strings = _shared_strings(zf, rel.target, budget)
            break
    for sheet_name, rel_id in sheets:
        sink.write(sheet_name + "\n")
        target = targets.get(rel_id or "")
        if target is not None:
            _write_sheet(zf, target, strings, sink, budget)
