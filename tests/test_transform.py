"""The ooxml_to_text transform, alone and in a Plone site."""

from c2.transform.ooxml import config
from c2.transform.ooxml.transform import ooxml_to_text
from c2.transform.ooxml.transform import register
from Products.PortalTransforms.data import datastream
from Products.PortalTransforms.interfaces import ITransform
from tests.builders import a_p
from tests.builders import build_docx
from tests.builders import build_pptx
from tests.builders import build_xlsx
from tests.builders import shape
from tests.builders import w_p
from tests.builders import x_row

import logging
import pytest


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
DOCM = "application/vnd.ms-word.document.macroEnabled.12"


def convert(orig: bytes | str) -> str:
    data = datastream("test")
    result = ooxml_to_text().convert(orig, data)
    assert result is data
    text: str = data.getData()
    return text


def test_implements_itransform():
    assert ITransform.providedBy(ooxml_to_text())


def test_name_and_mimetypes():
    t = register()
    assert t.name() == "ooxml_to_text"
    assert t.output == "text/plain"
    assert t.output_encoding == "utf-8"
    assert t.inputs == tuple(m["mimetypes"][0] for m in config.ooxml_mimetypes)
    assert len(t.inputs) == 14


def test_convert_bytes():
    assert convert(build_docx(w_p("本文"))) == "本文\n"


def test_convert_non_bytes_is_empty(caplog):
    with caplog.at_level(logging.WARNING, logger="c2.transform.ooxml"):
        assert convert("not bytes") == ""
    assert [r.getMessage() for r in caplog.records] == [
        "ooxml_to_text expects bytes, got str; no text is extracted"
    ]


@pytest.mark.parametrize(
    ("mimetype", "document", "expected"),
    [
        (DOCX, build_docx(w_p("本文")), "本文"),
        (DOCM, build_docx(w_p("マクロ付き")), "マクロ付き"),
        (XLSX, build_xlsx([("表", x_row("i:セル"))]), "セル"),
        (PPTX, build_pptx([(shape(a_p("スライド")), None)]), "スライド"),
    ],
)
def test_convert_in_plone(portal, mimetype, document, expected):
    out = portal.portal_transforms.convertTo("text/plain", document, mimetype=mimetype)
    assert out is not None
    assert expected in out.getData()


def test_convert_broken_file_in_plone(portal):
    out = portal.portal_transforms.convertTo(
        "text/plain", b"\xd0\xcf\x11\xe0broken", mimetype=DOCX
    )
    assert out is None or out.getData() == ""


def test_file_is_searchable(portal):
    from plone import api
    from plone.app.testing import setRoles
    from plone.app.testing import TEST_USER_ID
    from plone.namedfile.file import NamedBlobFile

    setRoles(portal, TEST_USER_ID, ["Manager"])
    api.content.create(
        container=portal,
        type="File",
        id="report",
        title="Report",
        file=NamedBlobFile(
            data=build_docx(w_p("Quarterly zebrafinch report")),
            contentType=DOCX,
            filename="report.docx",
        ),
    )
    found = api.content.find(SearchableText="zebrafinch")
    assert [b.getId for b in found] == ["report"]
