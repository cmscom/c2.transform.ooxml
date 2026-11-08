"""The text of Excel workbooks."""

from c2.transform.ooxml import config
from c2.transform.ooxml import package
from c2.transform.ooxml.excel import extract_excel
from c2.transform.ooxml.package import Budget
from c2.transform.ooxml.package import LimitReached
from c2.transform.ooxml.package import TextSink
from tests.builders import build_xlsx
from tests.builders import x_row

import io
import pytest
import zipfile


def excel_text(data: bytes) -> str:
    zf = zipfile.ZipFile(io.BytesIO(data))
    budget = Budget()
    sink = TextSink(budget)
    main = package.main_part(zf, budget)
    assert main is not None
    extract_excel(zf, main, sink, budget)
    return sink.text()


def test_sheet_names_and_values():
    data = build_xlsx([("名簿", x_row("s:0", "42"))], shared=["<s:t>氏名</s:t>"])
    assert excel_text(data) == "名簿\n氏名\t42\n"


def test_sheets_in_workbook_order():
    data = build_xlsx([
        ("一枚目", x_row("1")),
        ("二枚目", x_row("2")),
    ])
    assert excel_text(data) == "一枚目\n1\n二枚目\n2\n"


def test_shared_and_inline_strings():
    data = build_xlsx(
        [("S", x_row("s:1", "i:直接", "s:0"))],
        shared=[
            "<s:t>共有A</s:t>",
            "<s:r><s:t>共有</s:t></s:r><s:r><s:t>B</s:t></s:r>",
        ],
    )
    assert excel_text(data) == "S\n共有B\t直接\t共有A\n"


def test_formula_dropped_result_kept():
    data = build_xlsx([("S", x_row("1", "2", "f:SUM(A1:B1)=3"))])
    text = excel_text(data)
    assert "3" in text
    assert "SUM" not in text


def test_date_stays_number():
    cell = '<s:row><s:c s="1"><s:v>45000</s:v></s:c></s:row>'
    assert excel_text(build_xlsx([("S", cell)])) == "S\n45000\n"


def test_phonetic_excluded():
    si = "<s:t>漢字</s:t><s:rPh sb='0' eb='2'><s:t>カンジ</s:t></s:rPh>"
    text = excel_text(build_xlsx([("S", x_row("s:0"))], shared=[si]))
    assert "漢字" in text
    assert "カンジ" not in text


def test_phonetic_excluded_inline():
    cell = (
        '<s:row><s:c t="inlineStr"><s:is><s:t>漢字</s:t>'
        "<s:rPh sb='0' eb='2'><s:t>カンジ</s:t></s:rPh></s:is></s:c></s:row>"
    )
    text = excel_text(build_xlsx([("S", cell)]))
    assert "漢字" in text
    assert "カンジ" not in text


@pytest.mark.parametrize("index", ["5", "-1", "x", ""])
def test_bad_shared_index_skipped(index):
    data = build_xlsx([("S", x_row(f"s:{index}", "7"))], shared=["<s:t>A</s:t>"])
    assert excel_text(data) == "S\n7\n"


def test_boolean_error_and_str_cells():
    row = (
        "<s:row>"
        '<s:c t="b"><s:v>1</s:v></s:c>'
        '<s:c t="e"><s:v>#DIV/0!</s:v></s:c>'
        '<s:c t="str"><s:f>A1&amp;"x"</s:f><s:v>1x</s:v></s:c>'
        '<s:c t="n"/>'
        "</s:row>"
    )
    # A cell without a value (only formatted) is left out.
    assert excel_text(build_xlsx([("S", row)])) == "S\n1\t#DIV/0!\t1x\n"


def test_hidden_sheet_included():
    data = build_xlsx(
        [("表", x_row("1")), ("隠し", x_row("i:見えない"))], hidden=["隠し"]
    )
    assert "見えない" in excel_text(data)


def test_comments_not_read():
    comments = "<s:commentList><s:comment ref='A1'><s:text><s:t>注記</s:t></s:text></s:comment></s:commentList>"
    data = build_xlsx([("S", x_row("1"))], comments=comments)
    assert "注記" not in excel_text(data)


def test_empty_rows_and_sheets():
    data = build_xlsx([("空", ""), ("S", "<s:row/>" + x_row("1"))])
    assert excel_text(data) == "空\nS\n\n1\n"


def test_shared_strings_count_toward_the_text_limit(monkeypatch):
    # The strings are kept in memory even when no cell uses them.
    monkeypatch.setattr(config, "MAX_TEXT_CHARS", 10)
    data = build_xlsx([("S", x_row("s:0"))], shared=["<s:t>abcd</s:t>"] * 5)
    zf = zipfile.ZipFile(io.BytesIO(data))
    budget = Budget()
    sink = TextSink(budget)
    with pytest.raises(LimitReached):
        extract_excel(zf, "xl/workbook.xml", sink, budget)


@pytest.mark.parametrize("strict", [False, True])
def test_strict_excel(strict):
    data = build_xlsx(
        [("名簿", x_row("s:0", "i:直接", "42"))],
        shared=["<s:t>氏名</s:t>"],
        strict=strict,
    )
    assert excel_text(data) == "名簿\n氏名\t直接\t42\n"
