"""Tests of .github/scripts/release.py, which the release workflow runs."""

from pathlib import Path
from types import ModuleType

import importlib.util
import pytest
import sys


SCRIPT = Path(__file__).parents[1] / ".github" / "scripts" / "release.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_script", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_script"] = module
    spec.loader.exec_module(module)
    return module


release = load_script()

TYPES = ["breaking", "feature", "bugfix", "internal", "documentation", "tests"]
MAIN = "refs/heads/main"


def check(
    version: str = "1.0.0b2",
    current: str = "1.0.0b2.dev0",
    tags: tuple[str, ...] = ("1.0.0b1",),
    names: tuple[str, ...] = ("+fix.bugfix",),
    ref: str = MAIN,
) -> list[str]:
    errors: list[str] = release.check_release(
        version, current, list(tags), list(names), TYPES, ref
    )
    return errors


def test_a_good_release_has_no_errors():
    assert check() == []


@pytest.mark.parametrize(
    ("version", "current"),
    [
        ("1.0.0b2", "1.0.0b2.dev0"),
        ("1.0.0", "1.0.0b2.dev0"),
        ("1.0.0rc1", "1.0.0b2.dev0"),
        ("1.1.0", "1.0.0b2.dev0"),
        ("1.0.1", "1.0.0"),
        ("1.0.0.post1", "1.0.0"),
        ("2.0", "1.9.9"),
    ],
)
def test_versions_after_the_current_one(version, current):
    assert check(version, current) == []


@pytest.mark.parametrize(
    ("version", "error"),
    [
        ("", "'' is not a PEP 440 version"),
        ("v1.0.0b2", "'v1.0.0b2' is not in the normalized form '1.0.0b2'"),
        ("1.0.0-b2", "'1.0.0-b2' is not in the normalized form '1.0.0b2'"),
        ("1.0.0B2", "'1.0.0B2' is not in the normalized form '1.0.0b2'"),
        (" 1.0.0b2", "' 1.0.0b2' is not in the normalized form '1.0.0b2'"),
        ("1.0.0beta2", "'1.0.0beta2' is not in the normalized form '1.0.0b2'"),
        ("1.0.0b2\n", "'1.0.0b2\\n' is not in the normalized form '1.0.0b2'"),
        ("1.0.0 b2", "'1.0.0 b2' is not a PEP 440 version"),
        ("1.0.0b2;x", "'1.0.0b2;x' is not a PEP 440 version"),
        ("latest", "'latest' is not a PEP 440 version"),
        ("1.0.0b3.dev0", "1.0.0b3.dev0 is a development version"),
        ("1.0.0b2+local", "1.0.0b2+local has a local part"),
        ("1!1.0.0", "1!1.0.0 has an epoch"),
        ("1.0.0b2.post1", "1.0.0b2.post1 is both a pre-release and a post-release"),
        ("1.0.0rc1.post2", "1.0.0rc1.post2 is both a pre-release and a post-release"),
    ],
)
def test_bad_versions(version, error):
    assert check(version) == [error]


@pytest.mark.parametrize(
    ("version", "current"),
    [
        ("1.0.0b1", "1.0.0b2.dev0"),
        ("1.0.0b2", "1.0.0b2"),
        ("1.0.0a9", "1.0.0b2.dev0"),
        ("0.9", "1.0.0b2.dev0"),
    ],
)
def test_versions_not_after_the_current_one(version, current):
    assert check(version, current, tags=()) == [
        f"{version} is not after the version {current} in pyproject.toml"
    ]


def test_an_existing_tag():
    assert check(tags=("1.0.0b1", "1.0.0b2")) == ["The tag 1.0.0b2 exists already"]


@pytest.mark.parametrize(
    "names",
    [
        (),
        (".gitkeep", ".changelog_template.jinja"),
        ("README.md", "+fix.unknown", "feature", ".hidden.feature"),
    ],
)
def test_no_news_fragments(names):
    assert check(names=names) == ["There are no news fragments in news/"]


@pytest.mark.parametrize(
    "name",
    ["+fix.bugfix", "12.feature", "+x.breaking", "12.feature.1", "+a.b.documentation"],
)
def test_news_fragments(name):
    assert check(names=(".gitkeep", name)) == []


@pytest.mark.parametrize("ref", ["refs/heads/release", "refs/tags/1.0.0b1", ""])
def test_only_from_main(ref):
    assert check(ref=ref) == [f"Run the release from main, not from {ref!r}"]


def test_all_errors_at_once():
    assert check(
        version="1.0.0b1", tags=("1.0.0b1",), names=(), ref="refs/heads/x"
    ) == [
        "Run the release from main, not from 'refs/heads/x'",
        "1.0.0b1 is not after the version 1.0.0b2.dev0 in pyproject.toml",
        "The tag 1.0.0b1 exists already",
        "There are no news fragments in news/",
    ]


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.0.0b1", "1.0.0b2.dev0"),
        ("1.0.0a3", "1.0.0a4.dev0"),
        ("1.0.0rc1", "1.0.0rc2.dev0"),
        ("1.0.0", "1.0.1.dev0"),
        ("1.0", "1.1.dev0"),
        ("2", "3.dev0"),
        ("1.0.9", "1.0.10.dev0"),
        ("1.0.0.post1", "1.0.0.post2.dev0"),
        ("1.0.0b9", "1.0.0b10.dev0"),
    ],
)
def test_next_development_version(version, expected):
    assert release.next_development_version(version) == expected


def test_next_development_version_after_a_post_release():
    # A post-release fixes a release, so the next one is another
    # post-release, not the next release.
    assert release.next_development_version("1.0.0.post1") == "1.0.0.post2.dev0"


@pytest.mark.parametrize(
    "version", ["1.0.0b2.post1", "1.0.0b3.dev0", "1.0.0+local", "1!1.0.0"]
)
def test_no_next_development_version(version):
    with pytest.raises(ValueError, match="is not a version that can be released"):
        release.next_development_version(version)


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.0.0a1", True),
        ("1.0.0b2", True),
        ("1.0.0rc1", True),
        ("1.0.0", False),
        ("1.0.0.post1", False),
        ("2", False),
    ],
)
def test_is_prerelease(version, expected):
    assert release.is_prerelease(version) is expected


PYPROJECT = """\
[build-system]
requires = ["setuptools>=69.0"]

[project]
name = "c2.transform.ooxml"
version = "1.0.0b2.dev0"
description = "version = \\"not this\\""

[tool.other]
version = "9.9"
"""


def test_set_version_changes_only_the_project_version():
    assert release.set_version(PYPROJECT, "1.0.0b2") == PYPROJECT.replace(
        'version = "1.0.0b2.dev0"', 'version = "1.0.0b2"'
    )


def test_set_version_without_a_project_version():
    text = '[project]\nname = "x"\n\n[tool.other]\nversion = "9.9"\n'
    with pytest.raises(ValueError, match=r"No version in \[project\]"):
        release.set_version(text, "1.0.0")


def test_fragment_types_from_pyproject():
    text = (
        '[tool.towncrier]\ndirectory = "news/"\n\n'
        '[[tool.towncrier.type]]\ndirectory = "feature"\nname = "New"\n\n'
        '[[tool.towncrier.type]]\ndirectory = "bugfix"\nname = "Fixes"\n'
    )
    assert release.fragment_types(text) == ["feature", "bugfix"]


def test_fragment_types_of_this_package():
    text = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert release.fragment_types(text) == TYPES


def test_first_alpha_after_its_development_version():
    # The first release of this package is 1.0.0a1, from 1.0.0a1.dev0.
    assert check("1.0.0a1", "1.0.0a1.dev0", tags=()) == []
    assert release.is_prerelease("1.0.0a1") is True
    assert release.next_development_version("1.0.0a1") == "1.0.0a2.dev0"


def test_alpha_not_after_a_beta_development_version():
    # 1.0.0a1 comes before 1.0.0b1.dev0: the development version must be
    # 1.0.0a1.dev0 (or before) for the release of 1.0.0a1.
    assert check("1.0.0a1", "1.0.0b1.dev0", tags=()) == [
        "1.0.0a1 is not after the version 1.0.0b1.dev0 in pyproject.toml"
    ]
