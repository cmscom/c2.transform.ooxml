"""Reading the zip and the XML of a document, with limits."""

from c2.transform.ooxml import config
from c2.transform.ooxml import package
from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import LimitReached
from c2.transform.ooxml.package import Relationship
from c2.transform.ooxml.package import TextSink
from lxml import etree
from tests.builders import build_docx
from tests.builders import build_zip
from tests.builders import rels
from tests.builders import root_rels
from tests.builders import w_p

import io
import pytest
import zipfile


def open_zip(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data))


def texts(zf: zipfile.ZipFile, name: str, budget: Budget | None = None) -> list[str]:
    """The text of the elements, as their "end" events come."""
    budget = budget or Budget()
    return [
        el.text
        for event, el in package.iter_xml(zf, name, budget)
        if event == "end" and el.text
    ]


@pytest.mark.parametrize("strict", [False, True])
def test_main_part_transitional_and_strict(strict):
    zf = open_zip(build_docx(w_p("x"), strict=strict))
    assert package.main_part(zf, Budget()) == "word/document.xml"


def test_main_part_missing():
    zf = open_zip(build_zip({"a.xml": "<a/>"}))
    assert package.main_part(zf, Budget()) is None


def test_main_part_absolute_target():
    zf = open_zip(build_zip({"_rels/.rels": root_rels("/word/document.xml")}))
    assert package.main_part(zf, Budget()) == "word/document.xml"


def test_relationships_resolve_relative_and_skip_external():
    zf = open_zip(
        build_zip({
            "word/_rels/document.xml.rels": rels([
                ("rId1", "image", "../media/a.png"),
                ("rId2", "header", "header1.xml"),
                ("rId3", "hyperlink", "https://www.example.org/"),
                ("rId4", "footer", "/word/footer1.xml"),
                ("rId5", "header", "head%20er2.xml"),
            ])
        })
    )
    assert package.relationships(zf, "word/document.xml", Budget()) == [
        Relationship("rId1", "image", "media/a.png"),
        Relationship("rId2", "header", "word/header1.xml"),
        Relationship("rId4", "footer", "word/footer1.xml"),
        Relationship("rId5", "header", "word/head er2.xml"),
    ]


def test_relationships_outside_the_package_are_left_out():
    zf = open_zip(
        build_zip({
            "word/_rels/document.xml.rels": rels([
                ("rId1", "header", "../../../etc/passwd"),
            ])
        })
    )
    assert package.relationships(zf, "word/document.xml", Budget()) == []


def test_strict_relationship_kinds():
    zf = open_zip(
        build_zip({
            "word/_rels/document.xml.rels": rels(
                [("rId1", "header", "header1.xml")], strict=True
            )
        })
    )
    assert package.relationships(zf, "word/document.xml", Budget()) == [
        Relationship("rId1", "header", "word/header1.xml")
    ]


def test_relationships_without_rels_part():
    zf = open_zip(build_zip({"word/document.xml": "<a/>"}))
    assert package.relationships(zf, "word/document.xml", Budget()) == []


def test_missing_target_part():
    # The relationship points to a part that is not in the zip.
    data = build_docx(w_p("本文"), headers=[w_p("H")])
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(buffer, "w") as target,
    ):
        for item in source.infolist():
            if item.filename != "word/header1.xml":
                target.writestr(item, source.read(item))
    zf = open_zip(buffer.getvalue())
    [header] = [
        r
        for r in package.relationships(zf, "word/document.xml", Budget())
        if r.kind == "header"
    ]
    assert list(package.iter_xml(zf, header.target, Budget())) == []


def test_iter_xml_events_and_is_el():
    zf = open_zip(build_docx(w_p("一", "二")))
    events = [
        (event, el.tag.rsplit("}", 1)[-1])
        for event, el in package.iter_xml(zf, "word/document.xml", Budget())
    ]
    assert events[:3] == [("start", "document"), ("start", "body"), ("start", "p")]
    assert texts(zf, "word/document.xml") == ["一", "二"]


@pytest.mark.parametrize("strict", [False, True])
def test_is_el(strict):
    uri = (
        "http://purl.oclc.org/ooxml/wordprocessingml/main"
        if strict
        else "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    )
    el = etree.Element(f"{{{uri}}}t")
    assert package.is_el(el, "w", "t")
    assert not package.is_el(el, "w", "p")
    assert not package.is_el(el, "a", "t")
    assert not package.is_el(etree.Comment("c"), "w", "t")


def test_elements_are_cleared_after_end():
    zf = open_zip(build_docx(w_p("一") * 3))
    ended = []
    for event, el in package.iter_xml(zf, "word/document.xml", Budget()):
        if event == "end" and package.is_el(el, "w", "p"):
            ended.append(el)
    assert all(len(el) == 0 and el.text is None for el in ended)


class LyingZip:
    """A zip whose part gives more bytes than its declared size."""

    def __init__(self, zf: zipfile.ZipFile, content: bytes) -> None:
        self.zf = zf
        self.content = content

    def getinfo(self, name: str) -> zipfile.ZipInfo:
        info = self.zf.getinfo(name)
        info.file_size = 10
        return info

    def open(self, name: str) -> io.BytesIO:
        return io.BytesIO(self.content)

    def namelist(self) -> list[str]:
        return self.zf.namelist()


def test_part_size_limit_ignores_declared_size(monkeypatch):
    monkeypatch.setattr(config, "MAX_PART_BYTES", 1024)
    content = b"<a>" + b"x" * 4096 + b"</a>"
    zf = LyingZip(open_zip(build_zip({"a.xml": content})), content)
    assert zf.getinfo("a.xml").file_size == 10
    with pytest.raises(LimitReached):
        list(package.iter_xml(zf, "a.xml", Budget()))  # type: ignore[arg-type]


def test_part_size_limit_real_zip(monkeypatch):
    monkeypatch.setattr(config, "MAX_PART_BYTES", 1024)
    zf = open_zip(build_zip({"a.xml": b"<a>" + b"x" * 4096 + b"</a>"}))
    with pytest.raises(LimitReached):
        list(package.iter_xml(zf, "a.xml", Budget()))


def test_part_within_the_limit(monkeypatch):
    monkeypatch.setattr(config, "MAX_PART_BYTES", 1024)
    zf = open_zip(build_zip({"a.xml": b"<a>" + b"x" * 1000 + b"</a>"}))
    assert texts(zf, "a.xml") == ["x" * 1000]


def test_total_size_limit(monkeypatch):
    monkeypatch.setattr(config, "MAX_TOTAL_BYTES", 1500)
    part = b"<a>" + b"x" * 1000 + b"</a>"
    zf = open_zip(build_zip({"a.xml": part, "b.xml": part}))
    budget = Budget()
    assert texts(zf, "a.xml", budget) == ["x" * 1000]
    with pytest.raises(LimitReached):
        texts(zf, "b.xml", budget)


def test_part_count_limit(monkeypatch):
    monkeypatch.setattr(config, "MAX_PARTS", 2)
    zf = open_zip(build_zip({"a.xml": "<a/>", "b.xml": "<b/>", "c.xml": "<c/>"}))
    budget = Budget()
    texts(zf, "a.xml", budget)
    texts(zf, "b.xml", budget)
    with pytest.raises(LimitReached):
        texts(zf, "c.xml", budget)


def test_doctype_rejected():
    part = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'
    zf = open_zip(build_zip({"a.xml": part}))
    seen = []
    with pytest.raises(ValueError, match="DOCTYPE"):
        for _event, el in package.iter_xml(zf, "a.xml", Budget()):
            seen.append(el.text or "")
    assert "boom" not in "".join(seen)


def test_external_entity_not_read(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret-value")
    part = (
        '<?xml version="1.0"?>'
        f'<!DOCTYPE x [<!ENTITY e SYSTEM "file://{secret}">]><x>&e;</x>'
    )
    zf = open_zip(build_zip({"a.xml": part}))
    seen = []
    with pytest.raises(ValueError, match="DOCTYPE"):
        for _event, el in package.iter_xml(zf, "a.xml", Budget()):
            seen.append(etree.tostring(el, encoding="unicode"))
    assert "top-secret-value" not in "".join(seen)


def test_broken_xml():
    zf = open_zip(build_zip({"a.xml": "<a><b></a>"}))
    with pytest.raises(etree.XMLSyntaxError):
        list(package.iter_xml(zf, "a.xml", Budget()))


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_time_limit():
    clock = Clock()
    budget = Budget(clock=clock)
    budget.check_time()
    clock.now += config.TIME_LIMIT_SECONDS + 1
    with pytest.raises(LimitReached):
        budget.check_time()


def test_time_is_checked_while_reading():
    clock = Clock()
    budget = Budget(clock=clock)
    rows = "".join(f"<r>{i}</r>" for i in range(5000))
    zf = open_zip(build_zip({"a.xml": f"<a>{rows}</a>"}))
    count = 0
    with pytest.raises(LimitReached):
        for _event in package.iter_xml(zf, "a.xml", budget):
            count += 1
            if count == 10:
                clock.now += config.TIME_LIMIT_SECONDS + 1
    # Checked every 1000 events, not only at the end.
    assert count <= 1001


def test_text_sink_truncates(monkeypatch):
    monkeypatch.setattr(config, "MAX_TEXT_CHARS", 5)
    sink = TextSink(Budget())
    sink.write("abc")
    with pytest.raises(LimitReached):
        sink.write("defg")
    assert sink.text() == "abcde"


def test_text_sink_exactly_at_the_limit(monkeypatch):
    monkeypatch.setattr(config, "MAX_TEXT_CHARS", 5)
    sink = TextSink(Budget())
    sink.write("abcde")
    assert sink.text() == "abcde"
    with pytest.raises(LimitReached):
        sink.write("f")
    assert sink.text() == "abcde"


def test_limit_reached_names_the_limit(monkeypatch):
    monkeypatch.setattr(config, "MAX_PARTS", 0)
    with pytest.raises(LimitReached, match="parts"):
        Budget().take_part()


@pytest.mark.parametrize(
    "uri",
    [
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "http://purl.oclc.org/ooxml/officeDocument/relationships",
    ],
)
def test_r_id(uri):
    el = etree.Element("sheet", {f"{{{uri}}}id": "rId7"})
    assert package.r_id(el) == "rId7"


def test_r_id_missing():
    assert package.r_id(etree.Element("sheet", {"id": "rId7"})) is None


def test_comment_and_pi_before_the_root():
    # The root has no parent, but the comment and the PI are its previous
    # siblings.
    part = (
        '<?xml version="1.0"?><!-- made by a tool -->'
        '<?mso-application progid="Word.Document"?><a><b>x</b></a>'
    )
    zf = open_zip(build_zip({"a.xml": part}))
    assert texts(zf, "a.xml") == ["x"]
