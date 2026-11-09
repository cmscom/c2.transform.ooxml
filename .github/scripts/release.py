"""Steps of the release workflow (.github/workflows/release.yml).

    release.py check VERSION
        Stop unless VERSION can be released now: a normalized PEP 440
        version after the one in pyproject.toml, without a tag yet, with
        news fragments, run from main.
    release.py set-version VERSION
        Set the version in pyproject.toml.
    release.py back-to-development VERSION
        Set the version in pyproject.toml to the development version after
        VERSION (the way zest.releaser does) and print it.
    release.py prerelease VERSION
        Print "true" if VERSION is a pre-release (a, b or rc), else "false".

The functions do not read files or run git, so that the tests can call them.
Needs the packaging distribution.
"""

from packaging.version import InvalidVersion
from packaging.version import Version
from pathlib import Path

import argparse
import os
import re
import subprocess
import sys


if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


PYPROJECT = Path("pyproject.toml")
MAIN = "refs/heads/main"

_PROJECT_TABLE = re.compile(r"^\[project\][ \t]*$", re.MULTILINE)
_NEXT_TABLE = re.compile(r"^\[", re.MULTILINE)
_VERSION_LINE = re.compile(r'^(version[ \t]*=[ \t]*)"[^"\n]*"', re.MULTILINE)


def check_release(
    version: str,
    current: str,
    tags: list[str],
    names: list[str],
    types: list[str],
    ref: str,
) -> list[str]:
    """Return the reasons why version cannot be released, or []."""
    errors = []
    if ref != MAIN:
        errors.append(f"Run the release from main, not from {ref!r}")
    shape = _version_errors(version)
    if shape:
        return errors + shape
    if Version(version) <= Version(current):
        errors.append(f"{version} is not after the version {current} in pyproject.toml")
    if version in tags:
        errors.append(f"The tag {version} exists already")
    if not any(_is_fragment(name, types) for name in names):
        errors.append("There are no news fragments in news/")
    return errors


def _version_errors(version: str) -> list[str]:
    try:
        parsed = Version(version)
    except InvalidVersion:
        return [f"{version!r} is not a PEP 440 version"]
    if str(parsed) != version:
        return [f"{version!r} is not in the normalized form {str(parsed)!r}"]
    if parsed.is_devrelease:
        return [f"{version} is a development version"]
    if parsed.local is not None:
        return [f"{version} has a local part"]
    if parsed.epoch:
        return [f"{version} has an epoch"]
    if parsed.pre is not None and parsed.post is not None:
        # Such versions (a fix of a pre-release) are not needed here and are
        # easy to get wrong, so they are not made.
        return [f"{version} is both a pre-release and a post-release"]
    return []


def _is_fragment(name: str, types: list[str]) -> bool:
    # towncrier names fragments <name>.<type> or <name>.<type>.<counter>.
    return not name.startswith(".") and any(
        part in types for part in name.split(".")[1:]
    )


def next_development_version(version: str) -> str:
    """The development version after version, as zest.releaser makes it.

    1.0.0b1 gives 1.0.0b2.dev0, 1.0.0 gives 1.0.1.dev0, 1.0.0.post1 gives
    1.0.0.post2.dev0.
    """
    if _version_errors(version):
        raise ValueError(f"{version} is not a version that can be released")
    parsed = Version(version)
    release = ".".join(str(part) for part in parsed.release)
    if parsed.pre is not None:
        letter, number = parsed.pre
        return f"{release}{letter}{number + 1}.dev0"
    if parsed.post is not None:
        return f"{release}.post{parsed.post + 1}.dev0"
    parts = list(parsed.release)
    parts[-1] += 1
    return ".".join(str(part) for part in parts) + ".dev0"


def is_prerelease(version: str) -> bool:
    """Whether version is a pre-release (a, b or rc) for the GitHub Release."""
    return Version(version).is_prerelease


def set_version(text: str, version: str) -> str:
    """Return the text of pyproject.toml with version in [project].

    Changes only that line, so that the rest of the file stays as it is.
    """
    table = _PROJECT_TABLE.search(text)
    if table is None:
        raise ValueError("No [project] table")
    end = _NEXT_TABLE.search(text, table.end())
    stop = len(text) if end is None else end.start()
    line = _VERSION_LINE.search(text, table.end(), stop)
    if line is None:
        raise ValueError("No version in [project]")
    return f'{text[: line.start()]}{line.group(1)}"{version}"{text[line.end() :]}'


def fragment_types(text: str) -> list[str]:
    """The fragment types (directories) of towncrier in pyproject.toml."""
    types = tomllib.loads(text)["tool"]["towncrier"]["type"]
    return [str(item["directory"]) for item in types]


def _project_version() -> str:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _write_version(version: str) -> None:
    PYPROJECT.write_text(
        set_version(PYPROJECT.read_text(encoding="utf-8"), version),
        encoding="utf-8",
    )
    if _project_version() != version:
        raise SystemExit(f"pyproject.toml does not have the version {version}")


def _remote_tags() -> list[str]:
    out = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs", "origin"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line.split("refs/tags/", 1)[1] for line in out.splitlines()]


def _check(version: str) -> int:
    text = PYPROJECT.read_text(encoding="utf-8")
    news = Path(tomllib.loads(text)["tool"]["towncrier"]["directory"])
    errors = check_release(
        version,
        _project_version(),
        _remote_tags(),
        sorted(path.name for path in news.iterdir() if path.is_file()),
        fragment_types(text),
        os.environ.get("GITHUB_REF", ""),
    )
    for error in errors:
        print(f"::error::{error}")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "command",
        choices=["check", "set-version", "back-to-development", "prerelease"],
    )
    parser.add_argument("version")
    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(args.version)
    if args.command == "set-version":
        _write_version(args.version)
        return 0
    if args.command == "prerelease":
        print("true" if is_prerelease(args.version) else "false")
        return 0
    current = _project_version()
    if current != args.version:
        print(f"::error::pyproject.toml has {current}, not {args.version}")
        return 1
    following = next_development_version(args.version)
    _write_version(following)
    print(following)
    return 0


if __name__ == "__main__":
    sys.exit(main())
