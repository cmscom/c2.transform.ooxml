"""The text of PowerPoint presentations."""

from c2.transform.ooxml import package
from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import TextSink
from c2.transform.ooxml.powerpoint import extract_powerpoint
from tests.builders import a_p
from tests.builders import build_pptx
from tests.builders import shape

import io
import pytest
import zipfile


def powerpoint_text(data: bytes) -> str:
    zf = zipfile.ZipFile(io.BytesIO(data))
    budget = Budget()
    sink = TextSink(budget)
    main = package.main_part(zf, budget)
    assert main is not None
    extract_powerpoint(zf, main, sink, budget)
    return sink.text()


def test_slide_paragraphs():
    data = build_pptx([(shape(a_p("題"), a_p("本", "文")), None)])
    assert powerpoint_text(data) == "題\n本文\n"


def test_slides_in_presentation_order():
    # The first slide of the presentation is the part slide2.xml.
    data = build_pptx(
        [(shape(a_p("一枚目")), None), (shape(a_p("二枚目")), None)],
        file_order=(2, 1),
    )
    text = powerpoint_text(data)
    assert text.index("一枚目") < text.index("二枚目")


def test_line_break():
    paragraph = "<a:p><a:r><a:t>上</a:t></a:r><a:br/><a:r><a:t>下</a:t></a:r></a:p>"
    assert powerpoint_text(build_pptx([(shape(paragraph), None)])) == "上\n下\n"


def test_table_and_shape_text():
    table = (
        "<p:graphicFrame><a:graphic><a:graphicData><a:tbl><a:tr>"
        f"<a:tc><a:txBody>{a_p('表の左')}</a:txBody></a:tc>"
        f"<a:tc><a:txBody>{a_p('表の右')}</a:txBody></a:tc>"
        "</a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>"
    )
    group = f"<p:grpSp>{shape(a_p('図形'))}</p:grpSp>"
    text = powerpoint_text(build_pptx([(table + group, None)]))
    assert "表の左" in text
    assert "表の右" in text
    assert "表の左表の右" not in text
    assert "図形" in text


def test_notes_after_slide():
    data = build_pptx([
        (shape(a_p("本文")), shape(a_p("メモ"))),
        (shape(a_p("次")), None),
    ])
    assert powerpoint_text(data) == "本文\nメモ\n次\n"


def test_fallback_skipped():
    content = (
        "<mc:AlternateContent>"
        f"<mc:Choice Requires='p14'>{shape(a_p('一度'))}</mc:Choice>"
        f"<mc:Fallback>{shape(a_p('一度'))}</mc:Fallback>"
        "</mc:AlternateContent>"
    )
    assert powerpoint_text(build_pptx([(content, None)])).count("一度") == 1


def test_comments_not_read():
    # Modern comments keep their text in DrawingML paragraphs.
    comments = f"<p:cm><p:txBody>{a_p('指摘')}</p:txBody></p:cm>"
    data = build_pptx([(shape(a_p("本文")), None)], comments=comments)
    text = powerpoint_text(data)
    assert "本文" in text
    assert "指摘" not in text


def test_hidden_slide_included():
    data = build_pptx(
        [(shape(a_p("表")), None), (shape(a_p("見せない")), None)], hidden=(1,)
    )
    assert powerpoint_text(data) == "表\n見せない\n"


@pytest.mark.parametrize("strict", [False, True])
def test_strict_powerpoint(strict):
    data = build_pptx(
        [(shape(a_p("本文")), shape(a_p("メモ")))],
        strict=strict,
    )
    assert powerpoint_text(data) == "本文\nメモ\n"
