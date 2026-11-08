"""Build small Office Open XML documents for the tests.

Every document is made here from short made-up text; the tests do not use
files of unknown origin. ``strict=True`` uses the namespaces of ISO/IEC
29500 Strict instead of the Transitional ones.
"""

from collections.abc import Sequence
from xml.sax.saxutils import escape

import io
import zipfile


PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"

TRANSITIONAL = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
STRICT = {
    "w": "http://purl.oclc.org/ooxml/wordprocessingml/main",
    "s": "http://purl.oclc.org/ooxml/spreadsheetml/main",
    "p": "http://purl.oclc.org/ooxml/presentationml/main",
    "a": "http://purl.oclc.org/ooxml/drawingml/main",
    "r": "http://purl.oclc.org/ooxml/officeDocument/relationships",
}


def ns(strict: bool) -> dict[str, str]:
    return STRICT if strict else TRANSITIONAL


def rel_type(kind: str, strict: bool = False) -> str:
    """The URI of a relationship type such as "officeDocument"."""
    return f"{ns(strict)['r']}/{kind}"


def build_zip(parts: dict[str, str | bytes]) -> bytes:
    """A zip file with ``parts`` (text is written as UTF-8)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in parts.items():
            zf.writestr(name, content.encode() if isinstance(content, str) else content)
    return buffer.getvalue()


def rels(items: Sequence[tuple[str, str, str]], strict: bool = False) -> str:
    """A .rels part. ``items`` are (Id, kind or full type URI, Target);
    a Target that starts with "http" is an external one."""
    lines = []
    for rel_id, kind, target in items:
        type_uri = kind if "://" in kind else rel_type(kind, strict)
        mode = ' TargetMode="External"' if target.startswith("http") else ""
        lines.append(
            f'<Relationship Id="{rel_id}" Type="{type_uri}" '
            f'Target="{escape(target)}"{mode}/>'
        )
    return f'<Relationships xmlns="{PKG_REL}">{"".join(lines)}</Relationships>'


def root_rels(main: str, strict: bool = False) -> str:
    return rels([("rId1", "officeDocument", main)], strict)


def content_types() -> str:
    # The reader does not use it; real documents have it.
    return (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/></Types>'
    )


def xml(root: str, inner: str, strict: bool = False, extra: str = "") -> str:
    """``<root>`` with the namespace declarations of every prefix."""
    names = ns(strict)
    decls = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in names.items())
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<{root} {decls} xmlns:mc="{MC}"{extra}>{inner}</{root}>'


# Word


def w_p(*texts: str) -> str:
    """A Word paragraph with one run per text."""
    runs = "".join(f"<w:r><w:t>{escape(t)}</w:t></w:r>" for t in texts)
    return f"<w:p>{runs}</w:p>"


def build_docx(
    body: str,
    *,
    headers: Sequence[str] = (),
    footers: Sequence[str] = (),
    footnotes: str | None = None,
    endnotes: str | None = None,
    comments: str | None = None,
    extra_parts: dict[str, str | bytes] | None = None,
    strict: bool = False,
) -> bytes:
    """A Word document. ``body`` and the other arguments are the inner XML
    (with the prefix ``w``) of their part."""
    parts: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types(),
        "_rels/.rels": root_rels("word/document.xml", strict),
        "word/document.xml": xml("w:document", f"<w:body>{body}</w:body>", strict),
    }
    items = []
    for i, header in enumerate(headers, 1):
        items.append((f"rIdH{i}", "header", f"header{i}.xml"))
        parts[f"word/header{i}.xml"] = xml("w:hdr", header, strict)
    for i, footer in enumerate(footers, 1):
        items.append((f"rIdF{i}", "footer", f"footer{i}.xml"))
        parts[f"word/footer{i}.xml"] = xml("w:ftr", footer, strict)
    if footnotes is not None:
        items.append(("rIdFn", "footnotes", "footnotes.xml"))
        parts["word/footnotes.xml"] = xml("w:footnotes", footnotes, strict)
    if endnotes is not None:
        items.append(("rIdEn", "endnotes", "endnotes.xml"))
        parts["word/endnotes.xml"] = xml("w:endnotes", endnotes, strict)
    if comments is not None:
        items.append(("rIdC", "comments", "comments.xml"))
        parts["word/comments.xml"] = xml("w:comments", comments, strict)
    parts["word/_rels/document.xml.rels"] = rels(items, strict)
    parts.update(extra_parts or {})
    return build_zip(parts)


# Excel


def x_row(*values: str) -> str:
    """A row of cells: "s:<n>" is a shared string, "i:<text>" an inline
    string, "f:<formula>=<value>" a formula with its value, anything else a
    number."""
    cells = []
    for value in values:
        if value.startswith("s:"):
            cells.append(f'<s:c t="s"><s:v>{value[2:]}</s:v></s:c>')
        elif value.startswith("i:"):
            cells.append(
                f'<s:c t="inlineStr"><s:is><s:t>{escape(value[2:])}</s:t></s:is></s:c>'
            )
        elif value.startswith("f:"):
            formula, result = value[2:].split("=", 1)
            cells.append(f"<s:c><s:f>{escape(formula)}</s:f><s:v>{result}</s:v></s:c>")
        else:
            cells.append(f"<s:c><s:v>{escape(value)}</s:v></s:c>")
    return f"<s:row>{''.join(cells)}</s:row>"


def build_xlsx(
    sheets: Sequence[tuple[str, str]],
    *,
    shared: Sequence[str] = (),
    hidden: Sequence[str] = (),
    file_order: Sequence[int] | None = None,
    comments: str | None = None,
    strict: bool = False,
) -> bytes:
    """A workbook. ``sheets`` are (name, rows); ``shared`` are the inner XML
    of each ``s:si`` (with the prefix ``s``); ``file_order`` numbers the
    sheet parts differently (for example (2, 1) names the first sheet
    sheet2.xml)."""
    numbers = list(file_order or range(1, len(sheets) + 1))
    parts: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types(),
        "_rels/.rels": root_rels("xl/workbook.xml", strict),
    }
    sheet_list = []
    items = []
    for (name, rows), i in zip(sheets, numbers, strict=True):
        state = ' state="hidden"' if name in hidden else ""
        sheet_list.append(
            f'<s:sheet name="{escape(name)}" sheetId="{i}" r:id="rIdS{i}"{state}/>'
        )
        items.append((f"rIdS{i}", "worksheet", f"worksheets/sheet{i}.xml"))
        parts[f"xl/worksheets/sheet{i}.xml"] = xml(
            "s:worksheet", f"<s:sheetData>{rows}</s:sheetData>", strict
        )
    if shared:
        sis = "".join(f"<s:si>{si}</s:si>" for si in shared)
        parts["xl/sharedStrings.xml"] = xml("s:sst", sis, strict)
        items.append(("rIdSS", "sharedStrings", "sharedStrings.xml"))
    if comments is not None:
        parts["xl/comments1.xml"] = xml("s:comments", comments, strict)
        items.append(("rIdC", "comments", "comments1.xml"))
    parts["xl/workbook.xml"] = xml(
        "s:workbook", f"<s:sheets>{''.join(sheet_list)}</s:sheets>", strict
    )
    parts["xl/_rels/workbook.xml.rels"] = rels(items, strict)
    return build_zip(parts)


# PowerPoint


def a_p(*texts: str) -> str:
    """A DrawingML paragraph with one run per text."""
    runs = "".join(f"<a:r><a:t>{escape(t)}</a:t></a:r>" for t in texts)
    return f"<a:p>{runs}</a:p>"


def shape(*paragraphs: str) -> str:
    return f"<p:sp><p:txBody>{''.join(paragraphs)}</p:txBody></p:sp>"


def build_pptx(
    slides: Sequence[tuple[str, str | None]],
    *,
    file_order: Sequence[int] | None = None,
    hidden: Sequence[int] = (),
    comments: str | None = None,
    strict: bool = False,
) -> bytes:
    """A presentation. ``slides`` are (shapes, notes shapes or None) in the
    order of the presentation; ``file_order`` numbers the slide parts
    differently (for example (2, 1) names the first slide slide2.xml);
    ``hidden`` are the indexes (from 0) of hidden slides."""
    numbers = list(file_order or range(1, len(slides) + 1))
    parts: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types(),
        "_rels/.rels": root_rels("ppt/presentation.xml", strict),
    }
    ids = []
    items = []
    for i, ((shapes, notes), number) in enumerate(zip(slides, numbers, strict=True)):
        ids.append(f'<p:sldId id="{256 + i}" r:id="rIdSl{number}"/>')
        items.append((f"rIdSl{number}", "slide", f"slides/slide{number}.xml"))
        tree = f"<p:cSld><p:spTree>{shapes}</p:spTree></p:cSld>"
        show = ' show="0"' if i in hidden else ""
        parts[f"ppt/slides/slide{number}.xml"] = xml("p:sld", tree, strict, show)
        slide_items = []
        if notes is not None:
            notes_tree = f"<p:cSld><p:spTree>{notes}</p:spTree></p:cSld>"
            parts[f"ppt/notesSlides/notesSlide{number}.xml"] = xml(
                "p:notes", notes_tree, strict
            )
            slide_items.append((
                "rIdN",
                "notesSlide",
                f"../notesSlides/notesSlide{number}.xml",
            ))
        if comments is not None and i == 0:
            parts["ppt/comments/comment1.xml"] = xml("p:cmLst", comments, strict)
            slide_items.append(("rIdC", "comments", "../comments/comment1.xml"))
        parts[f"ppt/slides/_rels/slide{number}.xml.rels"] = rels(slide_items, strict)
    parts["ppt/presentation.xml"] = xml(
        "p:presentation", f"<p:sldIdLst>{''.join(ids)}</p:sldIdLst>", strict
    )
    parts["ppt/_rels/presentation.xml.rels"] = rels(items, strict)
    return build_zip(parts)
