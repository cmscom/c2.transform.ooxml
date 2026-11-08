"""Choosing the format, and what happens with broken or large files."""

from c2.transform.ooxml import config
from c2.transform.ooxml.extract import extract_text
from tests.builders import a_p
from tests.builders import build_docx
from tests.builders import build_pptx
from tests.builders import build_xlsx
from tests.builders import build_zip
from tests.builders import root_rels
from tests.builders import shape
from tests.builders import w_p
from tests.builders import x_row

import logging
import pytest


LOGGER = "c2.transform.ooxml"


def test_dispatch_each_format():
    assert extract_text(build_docx(w_p("文書"))) == "文書\n"
    assert extract_text(build_xlsx([("表", x_row("i:セル"))])) == "表\nセル\n"
    assert extract_text(build_pptx([(shape(a_p("スライド")), None)])) == "スライド\n"


@pytest.mark.parametrize("strict", [False, True])
def test_dispatch_strict(strict):
    assert extract_text(build_docx(w_p("文書"), strict=strict)) == "文書\n"


def test_macro_enabled_same_as_plain():
    data = build_docx(
        w_p("本文"),
        extra_parts={"word/vbaProject.bin": b"Attribute VB_Name = MacroSecret"},
    )
    text = extract_text(data)
    assert text == "本文\n"
    assert "MacroSecret" not in text


def test_not_zip_returns_empty(caplog):
    # A password-protected document is an OLE container, not a zip.
    data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"x" * 100
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert [r.levelname for r in caplog.records] == ["WARNING"]
    assert "BadZipFile" in caplog.text


def test_empty_bytes_returns_empty(caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(b"") == ""


def test_no_main_part_returns_empty(caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(build_zip({"a.xml": "<a/>"})) == ""
    assert caplog.records


def test_unknown_root_returns_empty():
    data = build_zip({
        "_rels/.rels": root_rels("doc.xml"),
        "doc.xml": "<other xmlns='urn:x'><t>text</t></other>",
    })
    assert extract_text(data) == ""


def test_main_part_missing_from_zip():
    assert extract_text(build_zip({"_rels/.rels": root_rels("doc.xml")})) == ""


def test_broken_xml_returns_empty(caplog):
    data = build_zip({
        "_rels/.rels": root_rels("word/document.xml"),
        "word/document.xml": (
            "<w:document xmlns:w='http://schemas.openxmlformats.org/"
            "wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>secret-body-text"
        ),
    })
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert "XMLSyntaxError" in caplog.text
    assert "secret-body-text" not in caplog.text


def replace_part(data: bytes, name: str, content: str) -> bytes:
    """``data`` with the part ``name`` replaced."""
    import io
    import zipfile

    source = zipfile.ZipFile(io.BytesIO(data))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.namelist():
            body = content.encode() if item == name else source.read(item)
            target.writestr(item, body)
    return buffer.getvalue()


def test_broken_header_keeps_the_body(caplog):
    # A broken part after the main part: the text read so far stays, as at
    # a limit.
    data = build_docx(
        w_p("本文"),
        headers=[w_p("H")],
        extra_parts={"word/header1.xml": "<w:hdr xmlns:w='x'><w:p>"},
    )
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == "本文\n"
    assert "XMLSyntaxError" in caplog.text


def test_broken_second_sheet_keeps_the_first(caplog):
    data = build_xlsx([("一", x_row("i:最初")), ("二", x_row("i:次"))])
    data = replace_part(data, "xl/worksheets/sheet2.xml", "<s:worksheet")
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == "一\n最初\n二\n"
    assert "XMLSyntaxError" in caplog.text


def test_broken_second_slide_keeps_the_first(caplog):
    data = build_pptx([(shape(a_p("最初")), None), (shape(a_p("次")), None)])
    data = replace_part(data, "ppt/slides/slide2.xml", "<p:sld")
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == "最初\n"
    assert "XMLSyntaxError" in caplog.text


def test_broken_shared_strings_give_no_text(caplog):
    # Nothing is written before the shared strings are read.
    data = build_xlsx([("S", x_row("s:0"))], shared=["<s:t>A</s:t>"])
    data = replace_part(data, "xl/sharedStrings.xml", "<s:sst")
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""


def test_doctype_returns_empty(caplog):
    data = build_zip({
        "_rels/.rels": root_rels("word/document.xml"),
        "word/document.xml": (
            '<!DOCTYPE x [<!ENTITY e "boom">]>'
            "<w:document xmlns:w='http://schemas.openxmlformats.org/"
            "wordprocessingml/2006/main'>&e;</w:document>"
        ),
    })
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert "ValueError" in caplog.text


def test_limit_returns_partial(monkeypatch, caplog):
    monkeypatch.setattr(config, "MAX_TEXT_CHARS", 3)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(build_docx(w_p("あいうえお"))) == "あいう"
    assert "text length" in caplog.text
    assert "あいう" not in caplog.text


class StepClock:
    """A clock that jumps past the time limit after some calls."""

    def __init__(self, calls_before_timeout: int) -> None:
        self.calls = 0
        self.limit = calls_before_timeout

    def __call__(self) -> float:
        self.calls += 1
        if self.calls > self.limit:
            return 1000.0 + config.TIME_LIMIT_SECONDS + 1
        return 1000.0


def test_time_limit_returns_partial(caplog):
    rows = "".join(x_row(f"i:行{i}") for i in range(2000))
    data = build_xlsx([("S", rows)])
    full = extract_text(data)
    counting = StepClock(10**9)
    extract_text(data, clock=counting)
    # Some point in time stops the reading inside the sheet: the text read
    # so far comes back, with a warning.
    partial = []
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        for calls in range(1, counting.calls):
            text = extract_text(data, clock=StepClock(calls))
            if len("S\n行0\n") <= len(text) < len(full):
                partial.append(text)
    assert partial
    assert all(full.startswith(text) for text in partial)
    assert "time" in caplog.text


def test_success_logs_nothing(caplog):
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        extract_text(build_docx(w_p("文書")))
    assert caplog.records == []


def _stored_docx() -> bytes:
    """A Word document whose parts are stored (not compressed)."""
    import io
    import zipfile

    source = zipfile.ZipFile(io.BytesIO(build_docx(w_p("本文"))))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
    return buffer.getvalue()


def _set_compression(data: bytes, method: int) -> bytes:
    """Change the compression method of every entry, in the local headers
    (offset 8) and in the central directory (offset 10)."""
    out = bytearray(data)
    for signature, offset in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
        start = 0
        while (start := out.find(signature, start)) != -1:
            out[start + offset : start + offset + 2] = method.to_bytes(2, "little")
            start += 4
    return bytes(out)


@pytest.mark.parametrize(
    "method",
    [
        9,  # Deflate64: zipfile cannot read it
        12,  # bzip2
        14,  # LZMA
        93,  # Zstandard (Python 3.14)
    ],
)
def test_other_compression_is_not_opened(monkeypatch, caplog, method):
    # Only stored and deflated entries are read: zipfile decompresses the
    # others without a limit on the size of the output.
    import zipfile

    data = _set_compression(_stored_docx(), method)
    opened = []
    open_entry = zipfile.ZipFile.open

    def recording_open(self, name, *args: object, **kwargs: object) -> object:
        opened.append(name)
        return open_entry(self, name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(zipfile.ZipFile, "open", recording_open)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert opened == []
    assert "UnsupportedCompression" in caplog.text


def test_other_compression_after_the_main_part(caplog):
    # A header in bzip2: the body stays, as for a broken part.
    import io
    import zipfile

    source = zipfile.ZipFile(io.BytesIO(build_docx(w_p("本文"), headers=[w_p("H")])))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as target:
        for name in source.namelist():
            method = (
                zipfile.ZIP_BZIP2
                if name == "word/header1.xml"
                else zipfile.ZIP_DEFLATED
            )
            target.writestr(name, source.read(name), compress_type=method)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(buffer.getvalue()) == "本文\n"
    assert "UnsupportedCompression" in caplog.text


def test_corrupt_compressed_data_returns_empty(caplog):
    # Stored data read as deflate: zlib.error.
    data = _set_compression(_stored_docx(), 8)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert caplog.records


def test_encrypted_entry_returns_empty(caplog):
    # The flag bit 0 (encrypted) in the central directory: RuntimeError.
    data = bytearray(_stored_docx())
    start = 0
    while (start := data.find(b"PK\x01\x02", start)) != -1:
        data[start + 8] |= 1
        start += 4
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(bytes(data)) == ""
    assert "RuntimeError" in caplog.text


def test_comment_before_the_root_of_a_part():
    data = build_zip({
        "_rels/.rels": root_rels("word/document.xml"),
        "word/document.xml": (
            '<?xml version="1.0"?><!-- generated -->'
            "<w:document xmlns:w='http://schemas.openxmlformats.org/"
            "wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>本文</w:t>"
            "</w:r></w:p></w:body></w:document>"
        ),
    })
    assert extract_text(data) == "本文\n"


def test_corrupt_lzma_data_returns_empty(caplog):
    # An entry compressed with LZMA (method 14), with valid LZMA properties
    # and then corrupt data, is refused before it is opened.
    import io
    import zipfile

    payload = b"\x09\x14\x05\x00\x5d\x00\x00\x10\x00" + b"\xff" * 64
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("_rels/.rels", payload)
    data = _set_compression(buffer.getvalue(), 14)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert "UnsupportedCompression" in caplog.text


def test_broken_xml_message_is_not_logged(caplog):
    # libxml2's message for a tag mismatch quotes the closing tag, so this
    # fails if the message (not only the type) is logged. (An undefined
    # entity does not do: with resolve_entities=False the message is only
    # "no element found".)
    data = build_zip({
        "_rels/.rels": root_rels("word/document.xml"),
        "word/document.xml": (
            "<w:document xmlns:w='http://schemas.openxmlformats.org/"
            "wordprocessingml/2006/main'><w:body><w:p><w:r>"
            "<w:t>x</w:secretword></w:r></w:p></w:body></w:document>"
        ),
    })
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert "XMLSyntaxError" in caplog.text
    assert "secretword" not in caplog.text


def _to_zip64(data: bytes, sentinels: bool = True) -> bytes:
    """``data`` with a Zip64 end of central directory (and its locator).

    The counts and sizes of the classic record are set to 0xFFFF... (the
    sentinels), or to 0 (zipfile still takes the Zip64 values)."""
    import struct

    pos = data.rfind(b"PK\x05\x06")
    _sig, _disk, _cd_disk, n_disk, n_total, cd_size, cd_offset, _comment = (
        struct.unpack_from("<4s4H2LH", data, pos)
    )
    zip64 = struct.pack(
        "<4sQ2H2L4Q",
        b"PK\x06\x06",
        44,
        45,
        45,
        0,
        0,
        n_disk,
        n_total,
        cd_size,
        cd_offset,
    )
    locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, pos, 1)
    if sentinels:
        eocd = struct.pack(
            "<4s4H2LH", b"PK\x05\x06", 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0
        )
    else:
        eocd = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 0, 0, 0, 0, 0)
    return data[:pos] + zip64 + locator + eocd


def _many_entries(count: int) -> bytes:
    """A Word document with ``count`` more empty entries."""
    import io
    import zipfile

    source = zipfile.ZipFile(io.BytesIO(build_docx(w_p("本文"))))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        for i in range(count):
            target.writestr(f"empty/{i}", b"")
    return buffer.getvalue()


@pytest.fixture
def zipfile_reads(monkeypatch):
    """The central directories that zipfile reads. Clear it after building
    the test document (building it reads zips too)."""
    import zipfile

    reads = []
    real = getattr(zipfile.ZipFile, "_RealGetContents")  # noqa: B009 (private)

    def recording(self) -> None:
        reads.append(self)
        real(self)

    monkeypatch.setattr(zipfile.ZipFile, "_RealGetContents", recording)
    return reads


def test_too_many_entries_are_not_read(monkeypatch, caplog, zipfile_reads):
    monkeypatch.setattr(config, "MAX_ENTRIES", 10)
    data = _many_entries(20)
    zipfile_reads.clear()
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert zipfile_reads == []
    assert "entries" in caplog.text


def test_entries_within_the_limit(monkeypatch, zipfile_reads):
    monkeypatch.setattr(config, "MAX_ENTRIES", 30)
    data = _many_entries(20)
    zipfile_reads.clear()
    assert extract_text(data) == "本文\n"
    assert len(zipfile_reads) == 1


def test_a_lying_count_of_entries(monkeypatch, caplog, zipfile_reads):
    # The end record says 1 entry; the central directory has 32.
    import struct

    monkeypatch.setattr(config, "MAX_ENTRIES", 10)
    data = bytearray(_many_entries(20))
    pos = data.rfind(b"PK\x05\x06")
    struct.pack_into("<2H", data, pos + 8, 1, 1)
    zipfile_reads.clear()
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(bytes(data)) == ""
    assert zipfile_reads == []


def test_central_directory_size_limit(monkeypatch, caplog, zipfile_reads):
    monkeypatch.setattr(config, "MAX_CENTRAL_DIRECTORY_BYTES", 100)
    data = build_docx(w_p("本文"))
    zipfile_reads.clear()
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert zipfile_reads == []
    assert "central directory" in caplog.text


def test_zip64_end_record():
    assert extract_text(_to_zip64(build_docx(w_p("本文")))) == "本文\n"


def test_zip64_too_many_entries(monkeypatch, caplog, zipfile_reads):
    monkeypatch.setattr(config, "MAX_ENTRIES", 10)
    data = _to_zip64(_many_entries(20))
    zipfile_reads.clear()
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert zipfile_reads == []


def _signature_in_offset(data: bytes) -> bytes:
    """``data`` with the offset of the central directory in the classic end
    record set to 0x06054b50, the bytes of the signature of that record.
    zipfile corrects the offset (it reads the directory just before the
    end record) and opens the zip."""
    import struct

    out = bytearray(data)
    pos = out.rfind(b"PK\x05\x06")
    struct.pack_into("<L", out, pos + 16, 0x06054B50)
    return bytes(out)


@pytest.mark.parametrize(
    ("limit", "value"), [("MAX_ENTRIES", 10), ("MAX_CENTRAL_DIRECTORY_BYTES", 100)]
)
@pytest.mark.parametrize("shape", ["zip64-without-sentinels", "signature-in-offset"])
def test_central_directory_check_is_not_bypassed(
    monkeypatch, caplog, zipfile_reads, limit, value, shape
):
    data = _many_entries(20)
    if shape == "zip64-without-sentinels":
        data = _to_zip64(data, sentinels=False)
    else:
        data = _signature_in_offset(data)
    zipfile_reads.clear()
    # Without the limit, zipfile reads the whole central directory of these
    # zips (the second gives no text later: its entries are misplaced).
    extract_text(data)
    assert len(zipfile_reads) == 1
    zipfile_reads.clear()
    monkeypatch.setattr(config, limit, value)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert zipfile_reads == []


def test_central_directory_cannot_be_checked(monkeypatch, caplog, zipfile_reads):
    # Without zipfile's own reading of the end records (a private function),
    # the zip is refused.
    from c2.transform.ooxml import package

    data = build_docx(w_p("本文"))
    monkeypatch.setattr(package, "_ZIPFILE_END_RECORD", "_NoSuchFunction")
    zipfile_reads.clear()
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert extract_text(data) == ""
    assert zipfile_reads == []
