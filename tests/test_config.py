from c2.transform.ooxml import config

import importlib
import mimetypes
import pytest


EXPECTED = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "dotx": "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    "docm": "application/vnd.ms-word.document.macroEnabled.12",
    "dotm": "application/vnd.ms-word.template.macroEnabled.12",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xltx": "application/vnd.openxmlformats-officedocument.spreadsheetml.template",
    "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    "xltm": "application/vnd.ms-excel.template.macroEnabled.12",
    "pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
    "potx": "application/vnd.openxmlformats-officedocument.presentationml.template",
    "ppsx": "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
    "pptm": "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
    "potm": "application/vnd.ms-powerpoint.template.macroEnabled.12",
    "ppsm": "application/vnd.ms-powerpoint.slideshow.macroEnabled.12",
}


@pytest.fixture
def stdlib_mimetypes_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forget the host's mime.types (slim images do not have one).

    mimetypes.init(files=[]) keeps the current database, so it is replaced.
    """
    monkeypatch.setattr(mimetypes, "_db", mimetypes.MimeTypes())


def test_mimetypes_table():
    names = {m["mimetypes"][0] for m in config.ooxml_mimetypes}
    assert len(names) == 14
    assert names == set(EXPECTED.values())
    # xlsb is binary, not XML.
    assert "application/vnd.ms-excel.sheet.binary.macroEnabled.12" not in names
    assert "application/vnd.ms-powerpoint.slideshow.macroEnabled.12" in names


def test_extensions():
    assert {m["extensions"][0]: m["mimetypes"][0] for m in config.ooxml_mimetypes} == (
        EXPECTED
    )


@pytest.mark.usefixtures("stdlib_mimetypes_only")
def test_import_adds_ooxml_types_to_stdlib_mimetypes():
    importlib.reload(config)
    assert {ext: mimetypes.guess_type(f"file.{ext}")[0] for ext in EXPECTED} == (
        EXPECTED
    )


def test_stdlib_guesses_docm():
    assert (
        mimetypes.guess_type("a.docm")[0]
        == "application/vnd.ms-word.document.macroEnabled.12"
    )


def test_ooxml_mimetypes_have_globs_and_icon():
    docx = next(m for m in config.ooxml_mimetypes if m["extensions"] == ("docx",))
    assert docx == {
        "name": "Office Word 2007 XML document",
        "mimetypes": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        "extensions": ("docx",),
        "globs": ("*.docx",),
        "icon_path": "application.png",
    }


def test_limits():
    assert config.TRANSFORM_NAME == "ooxml_to_text"
    assert config.MAX_PART_BYTES == 64 * 1024 * 1024
    assert config.MAX_TOTAL_BYTES == 256 * 1024 * 1024
    assert config.MAX_PARTS == 5000
    assert config.MAX_TEXT_CHARS == 10_000_000
    assert config.TIME_LIMIT_SECONDS == 30.0
    assert config.MAX_ENTRIES == 10_000
    assert config.MAX_CENTRAL_DIRECTORY_BYTES == 16 * 1024 * 1024
