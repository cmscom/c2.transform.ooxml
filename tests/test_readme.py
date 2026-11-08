"""The READMEs (English and Japanese) say the same essential things."""

from c2.transform.ooxml import config
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


README = ("README.md", "README-ja.md")


def test_readmes_link_each_other():
    assert "(README-ja.md)" in read("README.md")
    assert "(README.md)" in read("README-ja.md")


@pytest.mark.parametrize("readme", README)
def test_readmes_list_every_mimetype(readme):
    text = read(readme)
    for m in config.ooxml_mimetypes:
        assert f".{m['extensions'][0]}" in text
        assert m["mimetypes"][0] in text


@pytest.mark.parametrize("readme", README)
def test_readmes_state_limits(readme):
    text = read(readme)
    assert f"{config.MAX_PART_BYTES // (1024 * 1024)} MiB" in text
    assert f"{config.MAX_TOTAL_BYTES // (1024 * 1024)} MiB" in text
    assert f"{config.MAX_PARTS:,}" in text
    assert f"{config.MAX_TEXT_CHARS:,}" in text
    assert f"{config.TIME_LIMIT_SECONDS:g}" in text


@pytest.mark.parametrize("readme", README)
def test_readmes_name_the_other_package_and_reindexing(readme):
    text = read(readme)
    assert "c2.transform.msoffice" in text
    assert "manage_catalogRebuild" in text
    assert 'reindexObject(idxs=["SearchableText"])' in text
    assert ".xlsb" in text


def test_long_description_is_the_english_readme():
    # tomllib is not in Python 3.10.
    assert '\nreadme = "README.md"\n' in read("pyproject.toml")
