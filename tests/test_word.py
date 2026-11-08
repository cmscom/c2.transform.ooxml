"""The text of Word documents."""

from c2.transform.ooxml import package
from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import TextSink
from c2.transform.ooxml.word import extract_word
from tests.builders import build_docx
from tests.builders import w_p

import io
import pytest
import zipfile


def word_text(data: bytes) -> str:
    zf = zipfile.ZipFile(io.BytesIO(data))
    budget = Budget()
    sink = TextSink(budget)
    main = package.main_part(zf, budget)
    assert main is not None
    extract_word(zf, main, sink, budget)
    return sink.text()


def test_body_paragraphs():
    assert word_text(build_docx(w_p("一行目") + w_p("二行目"))) == "一行目\n二行目\n"


def test_runs_join_without_space():
    assert word_text(build_docx(w_p("漢", "字"))) == "漢字\n"


def test_tab_and_breaks():
    body = (
        "<w:p><w:r><w:t>a</w:t><w:tab/><w:t>b</w:t><w:br/><w:t>c</w:t>"
        "<w:cr/><w:t>d</w:t></w:r></w:p>"
    )
    assert word_text(build_docx(body)) == "a\tb\nc\nd\n"


def test_table_cells():
    body = (
        "<w:tbl><w:tr>"
        f"<w:tc>{w_p('左のセル')}</w:tc><w:tc>{w_p('右のセル')}</w:tc>"
        "</w:tr></w:tbl>"
    )
    text = word_text(build_docx(body))
    assert "左のセル" in text
    assert "右のセル" in text
    # Cells do not stick together.
    assert "左のセル右のセル" not in text


def test_header_footer_footnote_order():
    data = build_docx(
        w_p("B"),
        headers=[w_p("H")],
        footers=[w_p("F")],
        footnotes='<w:footnote w:id="1">' + w_p("N") + "</w:footnote>",
        endnotes='<w:endnote w:id="1">' + w_p("E") + "</w:endnote>",
    )
    assert word_text(data) == "B\nH\nF\nN\nE\n"


def test_inserted_kept_deleted_dropped():
    body = (
        "<w:p><w:ins><w:r><w:t>新</w:t></w:r></w:ins>"
        "<w:del><w:r><w:delText>旧</w:delText></w:r></w:del></w:p>"
    )
    text = word_text(build_docx(body))
    assert "新" in text
    assert "旧" not in text


def test_comments_not_read():
    comments = '<w:comment w:id="0">' + w_p("コメント") + "</w:comment>"
    text = word_text(build_docx(w_p("本文"), comments=comments))
    assert "本文" in text
    assert "コメント" not in text


def test_field_instruction_dropped():
    body = (
        "<w:p><w:r><w:fldChar w:fldCharType='begin'/></w:r>"
        "<w:r><w:instrText> PAGE </w:instrText></w:r>"
        "<w:r><w:fldChar w:fldCharType='separate'/></w:r>"
        "<w:r><w:t>3</w:t></w:r>"
        "<w:r><w:fldChar w:fldCharType='end'/></w:r></w:p>"
    )
    text = word_text(build_docx(body))
    assert "PAGE" not in text
    assert text == "3\n"


def test_textbox_once():
    textbox = "<w:txbxContent>" + w_p("箱") + "</w:txbxContent>"
    body = (
        "<w:p><w:r><mc:AlternateContent>"
        f"<mc:Choice Requires='wps'><w:drawing>{textbox}</w:drawing></mc:Choice>"
        f"<mc:Fallback><w:pict>{textbox}</w:pict></mc:Fallback>"
        "</mc:AlternateContent></w:r></w:p>"
    )
    text = word_text(build_docx(body))
    assert text.count("箱") == 1


def test_text_after_fallback_is_kept():
    body = (
        "<w:p><w:r><mc:AlternateContent>"
        "<mc:Choice Requires='wps'><w:t>前</w:t></mc:Choice>"
        "<mc:Fallback><w:t>前</w:t></mc:Fallback>"
        "</mc:AlternateContent><w:t>後</w:t></w:r></w:p>"
    )
    assert word_text(build_docx(body)) == "前後\n"


def test_whitespace_kept():
    body = '<w:p><w:r><w:t xml:space="preserve"> a  b </w:t></w:r></w:p>'
    assert word_text(build_docx(body)) == " a  b \n"


def test_empty_document():
    assert word_text(build_docx("")) == ""


@pytest.mark.parametrize("strict", [False, True])
def test_strict_word(strict):
    data = build_docx(
        w_p("本文"),
        headers=[w_p("H")],
        footnotes='<w:footnote w:id="1">' + w_p("N") + "</w:footnote>",
        strict=strict,
    )
    assert word_text(data) == "本文\nH\nN\n"


def test_tab_stops_are_not_text():
    # w:tab in the paragraph properties defines a tab stop.
    body = (
        '<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs>'
        "</w:pPr><w:r><w:t>a</w:t></w:r></w:p>"
    )
    assert word_text(build_docx(body)) == "a\n"


def test_moved_text_once():
    # A tracked move: the old place (w:moveFrom) and the new one (w:moveTo).
    body = (
        "<w:p><w:moveFrom w:id='1'><w:r><w:t>移す段落</w:t></w:r></w:moveFrom></w:p>"
        "<w:p><w:r><w:t>間</w:t></w:r></w:p>"
        "<w:p><w:moveTo w:id='2'><w:r><w:t>移す段落</w:t></w:r></w:moveTo></w:p>"
    )
    text = word_text(build_docx(body))
    assert text.count("移す段落") == 1
    assert text.index("間") < text.index("移す段落")
