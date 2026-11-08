"""The text of Excel workbooks (xlsx, xltx, xlsm, xltm).

``mc:Fallback`` repeats ``mc:Choice``, so it is skipped in every part.
"""

from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import is_el
from c2.transform.ooxml.package import iter_xml
from c2.transform.ooxml.package import r_id
from c2.transform.ooxml.package import relationships
from c2.transform.ooxml.package import TextSink
from c2.transform.ooxml.package import without_fallback

import zipfile


def _sheets(
    zf: zipfile.ZipFile, main: str, budget: Budget
) -> list[tuple[str, str | None]]:
    """(name, r:id) of every sheet, hidden ones too, in the workbook order."""
    return [
        (element.get("name") or "", r_id(element))
        for event, element in without_fallback(iter_xml(zf, main, budget))
        if event == "start" and is_el(element, "s", "sheet")
    ]


def _shared_strings(
    zf: zipfile.ZipFile, name: str, sink: TextSink, budget: Budget
) -> list[str]:
    """The shared strings. The phonetic reading (``s:rPh``) is left out.

    They are kept in memory, so they count toward the limit of the text,
    together with the text written to ``sink``.
    """
    strings: list[str] = []
    current: list[str] = []
    phonetic = 0
    for event, element in without_fallback(iter_xml(zf, name, budget)):
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
            sink.charge(len(text))
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


class _Cell:
    """The value of a cell (``s:c``) as it is read."""

    def __init__(self, cell_type: str | None) -> None:
        self.cell_type = cell_type
        # The text of s:v: the saved value, or the index of a shared string.
        self.value: str | None = None
        self.inline: list[str] = []

    def text(self, strings: list[str]) -> str | None:
        """The text of the cell, or None for a cell without a value."""
        if self.cell_type == "inlineStr":
            return "".join(self.inline)
        if self.cell_type == "s":
            return _shared(strings, self.value or "")
        return self.value


class _RowWriter:
    """Write the cells of a row one by one, separated by tabs."""

    def __init__(self, sink: TextSink) -> None:
        self.sink = sink
        self.first = True

    def cell(self, text: str) -> None:
        if not self.first:
            self.sink.write("\t")
        self.sink.write(text)
        self.first = False

    def end(self) -> None:
        self.sink.write("\n")
        self.first = True


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

    Each cell is written as it comes, not joined into a row first: a row
    of many cells that use one long shared string stops at the limit of
    the text before it is built.
    """
    row = _RowWriter(sink)
    cell: _Cell | None = None
    phonetic = 0
    for event, element in without_fallback(iter_xml(zf, name, budget)):
        if is_el(element, "s", "rPh"):
            phonetic += 1 if event == "start" else -1
        elif event == "start":
            if is_el(element, "s", "c"):
                cell = _Cell(element.get("t"))
        elif cell is not None and is_el(element, "s", "v"):
            cell.value = element.text or ""
        elif cell is not None and is_el(element, "s", "t") and not phonetic:
            cell.inline.append(element.text or "")
        elif cell is not None and is_el(element, "s", "c"):
            text = cell.text(strings)
            if text is not None:
                row.cell(text)
            cell = None
        elif is_el(element, "s", "row"):
            row.end()


def extract_excel(
    zf: zipfile.ZipFile, main: str, sink: TextSink, budget: Budget
) -> None:
    """Write the name of each sheet on a line, then its rows."""
    sheets = _sheets(zf, main, budget)
    sink.main_read = True
    rels = relationships(zf, main, budget)
    targets = {rel.rel_id: rel.target for rel in rels}
    strings: list[str] = []
    for rel in rels:
        if rel.kind == "sharedStrings":
            strings = _shared_strings(zf, rel.target, sink, budget)
            break
    for sheet_name, rel_id in sheets:
        sink.write(sheet_name + "\n")
        target = targets.get(rel_id or "")
        if target is not None:
            _write_sheet(zf, target, strings, sink, budget)
